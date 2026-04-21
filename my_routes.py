from flask import request, jsonify, send_file
from database import db, Player, Team, Match, Ranking
from datetime import datetime, timedelta
import random
import io
import csv
import math
from flask import redirect
def init_app(app):

        # --- 🔄 AUTO-ADVANCE LOGIC (The Brain) ---
    def advance_winner(match_id, winner_id):
        m = db.session.get(Match, match_id)
        if not m or not winner_id: return
        
        current_round_matches = Match.query.filter_by(category=m.category, draw_type=m.draw_type, round_no=m.round_no).order_by(Match.match_no.asc()).all()
        try: idx = current_round_matches.index(m)
        except ValueError: return
            
        is_qual = m.draw_type in ["Qual", "Qualification"]
        
        # 🚀 FIX 1: System check karega ki kya ye draw ka aakhri round hai?
        next_m = Match.query.filter_by(category=m.category, draw_type=m.draw_type, round_no=m.round_no + 1).order_by(Match.match_no.asc()).offset(idx // 2).first()
        
        if is_qual and not next_m:
            # 🏆 QUALIFICATION FINAL -> PROMOTE TO MAIN DRAW
            main_matches = Match.query.filter_by(category=m.category, draw_type="Main").order_by(Match.match_no.asc()).all()
            for mm in main_matches:
                mt1, mt2 = db.session.get(Team, mm.team1_id), db.session.get(Team, mm.team2_id)
                p1_obj = db.session.get(Player, mt1.player1_id) if mt1 else None
                p2_obj = db.session.get(Player, mt2.player1_id) if mt2 else None
                
                if p1_obj and p1_obj.draw_type == "Dummy" and "Qualifier" in p1_obj.name:
                    mt1.player1_id = winner_id
                    p1_obj.name = "Filled" 
                    break 
                elif p2_obj and p2_obj.draw_type == "Dummy" and "Qualifier" in p2_obj.name:
                    mt2.player1_id = winner_id
                    p2_obj.name = "Filled"
                    break
        elif next_m:
            # ➡️ ADVANCE TO NEXT ROUND
            nt1, nt2 = db.session.get(Team, next_m.team1_id), db.session.get(Team, next_m.team2_id)
            if idx % 2 == 0: nt1.player1_id = winner_id
            else: nt2.player1_id = winner_id
                
        db.session.commit()


    # --- 🌍 PAGE ROUTES ---
    @app.route('/')
    @app.route('/admin')
    def admin(): 
        # 1. Agar players hi nahi hain, toh seedha Setup par bhejo
        if Player.query.count() == 0: return redirect('/setup')
        # 2. Agar draws nahi bane hain, toh Draws page par bhejo
        if Match.query.count() == 0: return redirect('/draws')
        # 3. Sab theek hai toh Admin panel kholne do
        return send_file('admin.html')

    @app.route('/draws')
    def draws_page(): 
        # Bina player ke draw nahi ban sakta
        if Player.query.count() == 0: return redirect('/setup')
        return send_file('draws.html')

    @app.route('/seeding')
    def seeding_page(): 
        # Bina player ke seeding nahi ho sakti
        if Player.query.count() == 0: return redirect('/setup')
        # 🚀 STRICT LOCK: Agar matches generate ho gaye, toh Seeding change nahi kar sakte!
        if Match.query.count() > 0: return redirect('/admin') 
        return send_file('seeding.html')

    @app.route('/setup')
    def setup_page(): 
        # 🚀 STRICT LOCK: Agar tournament start ho chuka hai (koi match complete ho gaya), 
        # toh naya CSV upload block kar do taaki data corrupt na ho.
        if Match.query.filter_by(status="Completed").count() > 0: 
            return redirect('/admin')
        return send_file('setup.html')

    @app.route('/court/<int:court_num>')
    def umpire(court_num): 
        # Bina draw bane umpire kya karega? Wapas bhejo.
        if Match.query.count() == 0: return redirect('/draws')
        return send_file('scoring.html')

    @app.route('/live')
    def live_scoreboard(): return send_file('public.html')
    @app.route('/report')
    def report_page(): return send_file('report.html')

    
    # --- ⚙️ SETUP & SEEDING API ---
    @app.route('/api/upload_csv', methods=['POST'])
    def upload_csv():
        try:
            file = request.files.get('file')
            if not file: return jsonify({"success": False})
            stream = io.StringIO(file.stream.read().decode("utf-8", errors="ignore"), newline=None)
            csv_input = csv.DictReader(stream)
            for row in csv_input:
                name = row.get('Name', row.get('name', '')).strip()
                if name:
                    db.session.add(Player(name=name, category=row.get('Category', 'MS').strip(), rank=int(row.get('Rank', 0) or 0)))
            db.session.commit()
            return jsonify({"success": True})
        except: return jsonify({"success": False})

    @app.route('/api/get_categories')
    def get_categories():
        cats = db.session.query(Player.category).distinct().all()
        return jsonify([c[0] for c in cats if c[0]])

    @app.route('/api/get_entries/<category>')
    def get_entries(category):
        players = Player.query.filter_by(category=category).order_by(Player.rank.asc()).all()
        # 🚀 FIXED: Rank will now show properly in the UI
        return jsonify([{"id": p.id, "name": p.name, "draw_type": p.draw_type, "seed": p.seed, "rank": p.rank} for p in players])

    @app.route('/api/update_mq_status', methods=['POST'])
    def update_mq_status():
        # 🚀 FIXED: Seeding 'Save Changes' button will now work perfectly
        try:
            for data in request.json.get('updates', []):
                p = db.session.get(Player, int(data['id']))
                if p: 
                    p.draw_type = data['draw_type']
                    p.seed = int(data['seed']) if data['seed'] and str(data['seed']).isdigit() else 0
            db.session.commit()
            return jsonify({"success": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "error": str(e)})
    @app.route('/api/generate_draw',         methods=['POST'])
    def generate_draw():
        try:
            category, raw_type = request.json.get('category'), request.json.get('draw_type', 'Main')
            is_qual = raw_type in ["Qual", "Qualification"]
            std_type = "Qualification" if is_qual else "Main"
            
            # Duplicate Check
            if Match.query.filter_by(category=category, draw_type=std_type).first():
                return jsonify({"success": False, "error": f"Draw already generated for {category}!"})

            players = Player.query.filter(Player.category==category, Player.draw_type.in_(["Qual", "Qualification"] if is_qual else ["Main"])).all()
            if len(players) < 2: 
                return jsonify({"success": False, "error": "Not enough players!"})

            actual_count = len(players)
            bracket_size = 2 ** math.ceil(math.log2(actual_count)) if actual_count > 2 else 2
            byes_needed = bracket_size - actual_count
            
            seeds = sorted([p for p in players if p.seed > 0], key=lambda x: x.seed)
            unseeded = [p for p in players if p.seed == 0]
            random.shuffle(unseeded)

            draw_slots = [None] * bracket_size
            N = bracket_size

            # 🚀 1. PROFESSIONAL SEED SLOTS (National Standard)
            seed_slots = {
                1: 0,           # Match 1 Top
                2: N-1,         # Last Match Bottom
                3: N // 2,      # Match 9 Top (for 32)
                4: (N // 2) - 1,# Match 8 Bottom (for 32)
                5: N // 4,      # Match 5 Top
                6: (3 * N // 4) - 1, # Match 12 Bottom
                7: 3 * N // 4,  # Match 13 Top
                8: (N // 4) - 1 # Match 4 Bottom
            }

            for p in seeds:
                if p.seed in seed_slots:
                    draw_slots[seed_slots[p.seed]] = p

            # 🚀 2. PROFESSIONAL BYE PRIORITY
            bye_priority_indices = []
            for s_num in range(1, 9):
                if s_num in seed_slots:
                    idx = seed_slots[s_num]
                    opp_idx = idx + 1 if idx % 2 == 0 else idx - 1
                    bye_priority_indices.append(opp_idx)
            
            all_odds = [i for i in range(1, N, 2) if i not in bye_priority_indices]
            bye_priority_indices.extend(all_odds)

            # 🚀 3. QUALIFIER LOGIC FIX
            qual_count = Player.query.filter(Player.category==category, Player.draw_type.in_(["Qual", "Qualification"])).count()
            target_quals = 0
            if not is_qual and qual_count > 0:
                target_quals = max(1, qual_count // 2)

            for i in range(byes_needed):
                idx = bye_priority_indices[i]
                d_name = f"Bye {i+1}" if is_qual else (f"Qualifier {i+1}" if i < target_quals else f"Bye {i+1}")
                dp = Player(name=d_name, category=category, draw_type="Dummy")
                db.session.add(dp); db.session.flush()
                draw_slots[idx] = dp

            # 🚀 4. FILL THE REST
            remaining_seeds = [s for s in seeds if s.seed > 8]
            pool = remaining_seeds + unseeded
            for i in range(N):
                if draw_slots[i] is None and pool:
                    draw_slots[i] = pool.pop(0)

            # 🚀 5. GENERATE MATCHES & AUTO-ADVANCE
            last_match = Match.query.order_by(Match.match_no.desc()).first()
            start_no = (last_match.match_no + 1) if last_match else 1
            
            r1_matches = []
            for i in range(0, N, 2):
                p1, p2 = draw_slots[i], draw_slots[i+1]
                t1, t2 = Team(player1_id=p1.id), Team(player1_id=p2.id)
                db.session.add_all([t1, t2]); db.session.flush()
                
                status, winner_id = "Pending", None
                if "Bye" in p1.name: status, winner_id = "Completed", p2.id
                elif "Bye" in p2.name: status, winner_id = "Completed", p1.id
                
                m = Match(match_no=start_no, category=category, draw_type=std_type, team1_id=t1.id, team2_id=t2.id, status=status, winner_id=winner_id, round_no=1)
                db.session.add(m); r1_matches.append(m); start_no += 1

            # Future rounds logic
            curr = r1_matches; r_num = 2
            while len(curr) > (target_quals if is_qual else 1):
                nxt = []
                for i in range(0, len(curr), 2):
                    nt1, nt2 = Team(player1_id=None), Team(player1_id=None); db.session.add_all([nt1, nt2]); db.session.flush()
                    m = Match(match_no=start_no, category=category, draw_type=std_type, team1_id=nt1.id, team2_id=nt2.id, status="Pending", round_no=r_num)
                    db.session.add(m); nxt.append(m); start_no += 1
                curr = nxt; r_num += 1
            
            db.session.commit()
            for m in r1_matches:
                if m.status == "Completed": advance_winner(m.id, m.winner_id)
            return jsonify({"success": True})
        except Exception as e:
            db.session.rollback(); return jsonify({"success": False, "error": str(e)})

       
    # --- 🏸 MATCH MANAGEMENT ---
    @app.route('/api/finish_match/<int:match_id>', methods=['POST'])
    
    def finish_match(match_id):
        m = db.session.get(Match, match_id)
        if not m: return jsonify({"success": False})
        t1, t2 = db.session.get(Team, m.team1_id), db.session.get(Team, m.team2_id)
        
        if m.team1_score > m.team2_score: winner_id, loser_id = t1.player1_id, t2.player1_id
        else: winner_id, loser_id = t2.player1_id, t1.player1_id
            
        m.status, m.winner_id = "Completed", winner_id 
        m.completed_at = datetime.now()
        db.session.commit()
        
        advance_winner(match_id, winner_id)
        
        # 🚀 POINTS & RANKING LOGIC (RESTORED)
        def add_pts(pid, pts):
            r = Ranking.query.filter_by(player_id=pid, category=m.category).first()
            if not r: db.session.add(Ranking(player_id=pid, category=m.category, points=pts, tournaments_played=1))
            else: r.points += pts

        # BWF Style Points (Round 1: 10, Round 2: 20... Champion: 100)
        points_map = {1: 10, 2: 20, 3: 30, 4: 50, 5: 80} 
        add_pts(loser_id, points_map.get(m.round_no, 10))
        
        # Check if it's the Final Match (Main Draw)
        next_m = Match.query.filter_by(category=m.category, draw_type=m.draw_type, round_no=m.round_no + 1).first()
        if m.draw_type == "Main" and not next_m:
            add_pts(winner_id, 100) # Champion gets 100 points!
        
        # Rest Time (1 Min)
        p1, p2 = db.session.get(Player, t1.player1_id), db.session.get(Player, t2.player1_id)
        if p1: p1.is_playing, p1.rest_until = False, datetime.now() + timedelta(minutes=1)
        if p2: p2.is_playing, p2.rest_until = False, datetime.now() + timedelta(minutes=1)
        db.session.commit()
        return jsonify({"success": True})



    @app.route('/api/toggle_hold/<int:match_id>', methods=['POST'])
    def toggle_hold(match_id):
        m = db.session.get(Match, match_id)
        if not m: return jsonify({"success": False})
        if m.status == "Pending": m.status = "Hold"
        elif m.status == "Hold": m.status = "Pending"
        db.session.commit()
        return jsonify({"success": True, "new_status": m.status})

    @app.route('/api/admin_data')
    def admin_data():
        db.session.expire_all()
        now = datetime.now()
        active = []
        for m in Match.query.filter_by(status="On Court").all():
            t1, t2 = db.session.get(Team, m.team1_id), db.session.get(Team, m.team2_id)
            # 🚀 FIX: Sirf tabhi Player load karo jab player1_id NULL na ho
            p1 = db.session.get(Player, t1.player1_id) if (t1 and t1.player1_id is not None) else None
            p2 = db.session.get(Player, t2.player1_id) if (t2 and t2.player1_id is not None) else None

            active.append({"id": m.id, "category": f"#{m.match_no} | {m.category}", "court": m.court_number, "p1": p1.name if p1 else "TBD", "p2": p2.name if p2 else "TBD", "s1": m.team1_score, "s2": m.team2_score})
        
        pending = []
        all_p = Match.query.filter(Match.status.in_(["Pending", "Hold"])).all()
        all_p.sort(key=lambda x: (0 if x.draw_type in ["Qual", "Qualification"] else 1, x.match_no))
        for m in all_p:
            t1, t2 = db.session.get(Team, m.team1_id), db.session.get(Team, m.team2_id)
            # 🚀 FIX: Sirf tabhi Player fetch karo jab ID 'None' ना हो
            p1 = db.session.get(Player, t1.player1_id) if (t1 and t1.player1_id is not None) else None
            p2 = db.session.get(Player, t2.player1_id) if (t2 and t2.player1_id is not None) else None

            
            p1_n = p1.name if p1 else "TBD"
            p2_n = p2.name if p2 else "TBD"
            
            ready = True
            if not p1 or not p2 or (p1.rest_until and p1.rest_until > now) or (p2.rest_until and p2.rest_until > now): ready = False
            
            locked = False
            reason = ""
            quals_run = Match.query.filter(Match.category==m.category, Match.draw_type.in_(["Qual", "Qualification"]), Match.status!="Completed").first() is not None
            if "Qualifier" in p1_n or "Qualifier" in p2_n: locked, reason = True, "⏳ Waiting for Qualifiers"
            elif m.draw_type == "Main" and quals_run: locked, reason = True, "⏳ Qualifiers Running"
            elif not p1 or not p2: locked, reason = True, "⏳ Waiting for Prev Round"

            pending.append({"id": m.id, "category": f"#{m.match_no} | {m.category} - {m.draw_type}", "p1": p1_n, "p2": p2_n, "is_ready": ready, "is_locked": locked, "lock_reason": reason, "status": m.status})
        
        return jsonify({"active": active, "pending": pending})

    @app.route('/api/get_results')
    def get_results():
        res = []
        # 🚀 FIX 2: Ab result TIME ke hisaab se sort honge (Highest to Lowest)
        for m in Match.query.filter(Match.status=="Completed").order_by(Match.completed_at.desc()).limit(10).all():
            t1, t2 = db.session.get(Team, m.team1_id), db.session.get(Team, m.team2_id)
            p1, p2 = db.session.get(Player, t1.player1_id), db.session.get(Player, t2.player1_id)
            if p1 and p2:
                winner_is_p1 = (m.winner_id == p1.id)
                w_n, l_n = (p1.name, p2.name) if winner_is_p1 else (p2.name, p1.name)
                
                # 🚀 FIX 3: Pure history score ko flip karna (21-0, 21-0 format)
                hist_parts = []
                if m.score_history:
                    for game in m.score_history.split(','):
                        pts = game.split('-')
                        if len(pts) == 2:
                            # Agar Team 2 jeeti hai, toh score reverse karo
                            hist_parts.append(f"{pts[0].strip()}-{pts[1].strip()}" if winner_is_p1 else f"{pts[1].strip()}-{pts[0].strip()}")
                
                hist_str = ", ".join(hist_parts)
                s_win, s_loss = (m.team1_score, m.team2_score) if winner_is_p1 else (m.team2_score, m.team1_score)
                full_score = f"{hist_str}, {s_win}-{s_loss}" if hist_str else f"{s_win}-{s_loss}"
                
                res.append({"category": f"{m.category} - {m.draw_type}", "winner_name": w_n, "loser_name": l_n, "full_score": full_score})
        return jsonify(res)

    @app.route('/api/get_all_results')
    def get_all_results():
        res = []
        # order_by match_no kiya hai taaki Round 1 pehle dikhe aur Final sabse aakhri me
        for m in Match.query.filter(Match.status=="Completed").order_by(Match.category, Match.match_no).all():
            t1, t2 = db.session.get(Team, m.team1_id), db.session.get(Team, m.team2_id)
            p1, p2 = db.session.get(Player, t1.player1_id), db.session.get(Player, t2.player1_id)
            if p1 and p2:
                winner_is_p1 = (m.winner_id == p1.id)
                w_n, l_n = (p1.name, p2.name) if winner_is_p1 else (p2.name, p1.name)
                
                # 🚀 FIX: Agar loser ya winner koi "Bye" hai, toh usko PDF report me mat dikhao
                if "Bye" in w_n or "Bye" in l_n:
                    continue

                hist_parts = []
                if m.score_history:
                    for game in m.score_history.split(','):
                        pts = game.split('-')
                        if len(pts) == 2:
                            hist_parts.append(f"{pts[0].strip()}-{pts[1].strip()}" if winner_is_p1 else f"{pts[1].strip()}-{pts[0].strip()}")
                hist_str = ", ".join(hist_parts)
                s_win, s_loss = (m.team1_score, m.team2_score) if winner_is_p1 else (m.team2_score, m.team1_score)
                
                # Agar kisi wajah se match bina khele jeeta gaya hai (Walkover)
                if s_win == 0 and s_loss == 0 and not hist_str:
                    full_score = "W/O (Walkover)"
                else:
                    full_score = f"{hist_str}, {s_win}-{s_loss}" if hist_str else f"{s_win}-{s_loss}"
                
                res.append({"category": m.category, "draw": m.draw_type, "round": f"R{m.round_no}", "winner_name": w_n, "loser_name": l_n, "full_score": full_score})
        return jsonify(res)

    @app.route('/api/assign_court/<int:match_id>', methods=['POST'])
    def assign_court(match_id):
        m = db.session.get(Match, match_id); court = request.json['court_number']
        if Match.query.filter_by(court_number=court, status="On Court").first(): return jsonify({"success": False, "error": "Busy"})
        m.court_number, m.status = court, "On Court"
        db.session.commit(); return jsonify({"success": True})

    @app.route('/api/update_score/<int:match_id>', methods=['POST'])
    def update_score(match_id):
        m = db.session.get(Match, match_id)
        if m: m.team1_score, m.team2_score, m.score_history = request.json['s1'], request.json['s2'], request.json.get('history','')
        db.session.commit(); return jsonify({"success": True})
    
    @app.route('/api/court_match/<int:court_num>')
    def get_court_match(court_num):
        m = Match.query.filter_by(court_number=court_num, status="On Court").first()
        if m:
            t1, t2 = db.session.get(Team, m.team1_id), db.session.get(Team, m.team2_id)
            return jsonify({"success": True, "match_id": m.id, "team1": db.session.get(Player, t1.player1_id).name, "team2": db.session.get(Player, t2.player1_id).name, "s1": m.team1_score, "s2": m.team2_score})
        return jsonify({"success": False})
    # --- 📊 RANKINGS PAGE & API ---
    @app.route('/rankings')
    def rankings_page(): return send_file('rankings.html')

    @app.route('/api/get_rankings/<category>')
    def get_rankings(category):
        rankings = Ranking.query.filter_by(category=category).order_by(Ranking.points.desc()).all()
        return jsonify([{"rank": i + 1, "name": r.player.name if r.player else "Unknown", "played": r.tournaments_played, "points": r.points} for i, r in enumerate(rankings)])
    # --- 🌳 BRACKET VIEWER PAGE & API ---
    @app.route('/bracket')
    def bracket_page(): 
        return send_file('bracket.html')
    @app.route('/api/get_bracket/<category>/<draw_type>')
    def get_bracket(category, draw_type):
        matches = Match.query.filter_by(category=category, draw_type=draw_type).order_by(Match.round_no, Match.match_no).all()
        
        rounds_dict = {}
        for m in matches:
            r = m.round_no
            if r not in rounds_dict: rounds_dict[r] = []
            
            t1, t2 = db.session.get(Team, m.team1_id), db.session.get(Team, m.team2_id)
            p1 = db.session.get(Player, t1.player1_id) if t1 and t1.player1_id else None
            p2 = db.session.get(Player, t2.player1_id) if t2 and t2.player1_id else None
            
            # 🚀 FULL SCORE LOGIC: Yahan history banna zaroori hai
            f_score = ""
            if m.status == "Completed" and p1 and p2:
                winner_is_p1 = (m.winner_id == p1.id)
                hist_parts = []
                if m.score_history:
                    for game in m.score_history.split(','):
                        pts = game.split('-')
                        if len(pts) == 2:
                            hist_parts.append(f"{pts[0].strip()}-{pts[1].strip()}" if winner_is_p1 else f"{pts[1].strip()}-{pts[0].strip()}")
                hist_str = ", ".join(hist_parts)
                s_win, s_loss = (m.team1_score, m.team2_score) if winner_is_p1 else (m.team2_score, m.team1_score)
                f_score = f"{hist_str}, {s_win}-{s_loss}" if hist_str else f"{s_win}-{s_loss}"

            rounds_dict[r].append({
                "m_no": m.match_no,
                "p1": p1.name if p1 else "TBD",
                "p2": p2.name if p2 else "TBD",
                "full_score": f_score, # 👈 Yeh line missing thi!
                "w_id": m.winner_id,
                "p1_id": p1.id if p1 else None,
                "p2_id": p2.id if p2 else None,
                "status": m.status
            })
        
        bracket_data = [{"round": k, "matches": rounds_dict[k]} for k in sorted(rounds_dict.keys())]
        return jsonify(bracket_data)
