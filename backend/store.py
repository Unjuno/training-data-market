"""SQLite store for multi-browser votes, round freezing and immutable logs."""
from __future__ import annotations

import sqlite3
import os
import time
import secrets
from contextlib import contextmanager
from pathlib import Path

class GameError(Exception):
    def __init__(self, message: str, status_code:int=400):
        super().__init__(message)
        self.status_code=status_code

class GameStore:
    def __init__(self, location: str|Path):
        self.location=str(location)

    @contextmanager
    def _db(self,write=False):
        connection=sqlite3.connect(self.location,timeout=20,isolation_level=None)
        connection.row_factory=sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=20000')
        try:
            connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        Path(self.location).parent.mkdir(parents=True,exist_ok=True)
        with self._db(True) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS samples (
                  id INTEGER PRIMARY KEY, label INTEGER NOT NULL CHECK(label BETWEEN 0 AND 9),
                  version TEXT NOT NULL, available INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS rounds (
                  id TEXT PRIMARY KEY, checkpoint TEXT NOT NULL, target_a INTEGER NOT NULL,
                  target_b INTEGER NOT NULL, seed INTEGER NOT NULL, status TEXT NOT NULL,
                  opened_at REAL NOT NULL, closes_at REAL, locked_at REAL, finished_at REAL,
                  result_json TEXT, worker_token TEXT, worker_started_at REAL,
                  worker_attempts INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS picks (
                  round_id TEXT NOT NULL REFERENCES rounds(id),
                  user_id TEXT NOT NULL, sample_id INTEGER NOT NULL REFERENCES samples(id),
                  created_at REAL NOT NULL,
                  PRIMARY KEY(round_id,user_id,sample_id));
                CREATE INDEX IF NOT EXISTS idx_picks_round_sample ON picks(round_id,sample_id);
                CREATE TABLE IF NOT EXISTS recommendation_notes (
                  round_id TEXT NOT NULL REFERENCES rounds(id), user_id TEXT NOT NULL,
                  content TEXT NOT NULL CHECK(length(content)<=400),
                  PRIMARY KEY(round_id,user_id));
                CREATE TABLE IF NOT EXISTS forecasts (
                  round_id TEXT NOT NULL REFERENCES rounds(id),
                  user_id TEXT NOT NULL,
                  probability_pct INTEGER NOT NULL CHECK(probability_pct BETWEEN 5 AND 95 AND probability_pct % 5=0),
                  updated_at REAL NOT NULL,
                  PRIMARY KEY(round_id,user_id));
                CREATE TABLE IF NOT EXISTS events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, round_id TEXT,
                  kind TEXT NOT NULL, details TEXT NOT NULL, at REAL NOT NULL);
            ''')
            # Migrate v0.8 databases without deleting existing votes or rounds.
            columns={row['name'] for row in conn.execute('PRAGMA table_info(rounds)')}
            if 'closes_at' not in columns:
                conn.execute('ALTER TABLE rounds ADD COLUMN closes_at REAL')
            for field, ddl in (
                ('worker_token', 'TEXT'),
                ('worker_started_at', 'REAL'),
                ('worker_attempts', 'INTEGER NOT NULL DEFAULT 0'),
            ):
                if field not in columns:
                    conn.execute(f'ALTER TABLE rounds ADD COLUMN {field} {ddl}')
            fallback=self._round_seconds(None)
            conn.execute('UPDATE rounds SET closes_at=opened_at+? WHERE closes_at IS NULL', (fallback,))

    @staticmethod
    def _round_seconds(value:int|None)->int:
        duration=int(value if value is not None else os.getenv('TDM_ROUND_SECONDS', '86400'))
        if not 10<=duration<=604800:
            raise ValueError('round duration must be 10..604800 seconds')
        return duration

    def bootstrap_samples(self, samples, version:str):
        with self._db(True) as conn:
            if conn.execute("SELECT 1 FROM rounds LIMIT 1").fetchone():
                raise GameError('cannot change candidate pool after rounds were created',409)
            conn.executemany('INSERT INTO samples(id,label,version) VALUES(?,?,?)',
                             [(int(i),int(y),version) for i,y in samples])

    def open_round(self, round_id:str, checkpoint:str,targets:tuple[int,int],seed:int,
                   duration_seconds:int|None=None):
        a,b=targets
        duration=self._round_seconds(duration_seconds)
        with self._db(True) as conn:
            if conn.execute("SELECT 1 FROM rounds WHERE status IN ('OPEN','LOCKED','TRAINING') LIMIT 1").fetchone():
                raise GameError('another round is active',409)
            opened=time.time()
            conn.execute('INSERT INTO rounds(id,checkpoint,target_a,target_b,seed,status,opened_at,closes_at) VALUES(?,?,?,?,?,?,?,?)',
                         (round_id,checkpoint,a,b,seed,'OPEN',opened,opened+duration))

    def list_rounds(self,limit:int=20)->list[dict]:
        with self._db() as conn:
            return [dict(row) for row in conn.execute(
                'SELECT id,checkpoint,target_a,target_b,status,opened_at,closes_at,locked_at,finished_at '
                'FROM rounds ORDER BY opened_at DESC,id DESC LIMIT ?', (limit,))]

    def get_round(self, round_id:str) -> dict:
        with self._db() as conn:
            r=conn.execute('SELECT * FROM rounds WHERE id=?',(round_id,)).fetchone()
            if r is None:raise GameError('round not found',404)
            return dict(r)

    def current_round(self):
        with self._db() as conn:
            r=conn.execute('SELECT * FROM rounds ORDER BY opened_at DESC,id DESC LIMIT 1').fetchone()
            return dict(r) if r else None

    def _check_open(self,conn,round_id):
        r=conn.execute('SELECT status,closes_at FROM rounds WHERE id=?',(round_id,)).fetchone()
        if r is None:raise GameError('round not found',404)
        if r['status']!='OPEN':raise GameError('round is closed',409)
        if r['closes_at'] is None or time.time()>=r['closes_at']:
            raise GameError('voting deadline has passed',409)

    def set_pick(self, round_id:str, user_id:str,sample_id:int)->str:
        with self._db(True) as conn:
            self._check_open(conn,round_id)
            if not conn.execute('SELECT 1 FROM samples WHERE id=? AND available=1',(sample_id,)).fetchone():
                raise GameError('not an eligible image',404)
            if conn.execute('SELECT 1 FROM picks WHERE round_id=? AND user_id=? AND sample_id=?',
                            (round_id,user_id,sample_id)).fetchone():return 'exists'
            count=conn.execute('SELECT count(*) FROM picks WHERE round_id=? AND user_id=?',
                               (round_id,user_id)).fetchone()[0]
            if count>=10:raise GameError('maximum 10 images per user and round',409)
            conn.execute('INSERT INTO picks(round_id,user_id,sample_id,created_at) VALUES(?,?,?,?)',
                         (round_id,user_id,sample_id,time.time()))
            return 'created'

    def delete_pick(self,round_id:str,user_id:str,sample_id:int)->bool:
        with self._db(True) as conn:
            self._check_open(conn,round_id)
            result=conn.execute('DELETE FROM picks WHERE round_id=? AND user_id=? AND sample_id=?',
                                (round_id,user_id,sample_id))
            return result.rowcount>0

    def get_picks(self,round_id:str,user_id:str)->list[int]:
        with self._db() as conn:
            return [x[0] for x in conn.execute('SELECT sample_id FROM picks WHERE round_id=? AND user_id=? ORDER BY created_at,sample_id',
                                               (round_id,user_id)).fetchall()]

    def get_counts(self,round_id:str)->dict[int,int]:
        with self._db() as conn:
            return {int(r[0]):int(r[1]) for r in conn.execute(
                'SELECT sample_id,count(*) FROM picks WHERE round_id=? GROUP BY sample_id',(round_id,))}

    def get_classes(self):
        with self._db() as conn:
            return {int(r[0]):int(r[1]) for r in conn.execute('SELECT id,label FROM samples WHERE available=1')}

    def set_note(self,round_id:str,user_id:str,content:str)->str:
        if not isinstance(content,str) or len(content)>400:
            raise GameError('recommendation note is limited to 400 characters',422)
        with self._db(True) as conn:
            self._check_open(conn,round_id)
            conn.execute('INSERT INTO recommendation_notes(round_id,user_id,content) VALUES(?,?,?) '
                         'ON CONFLICT(round_id,user_id) DO UPDATE SET content=excluded.content',
                         (round_id,user_id,content))
            return 'saved'

    def get_note(self,round_id:str,user_id:str)->str:
        with self._db() as conn:
            r=conn.execute('SELECT content FROM recommendation_notes WHERE round_id=? AND user_id=?',
                           (round_id,user_id)).fetchone()
            return r['content'] if r else ''

    def set_forecast(self,round_id:str,user_id:str,probability_pct:int)->str:
        if type(probability_pct) is not int or not (5<=probability_pct<=95 and probability_pct%5==0):
            raise GameError('probability must be 5..95 in steps of 5',422)
        with self._db(True) as conn:
            self._check_open(conn,round_id)
            existing=conn.execute('SELECT probability_pct FROM forecasts WHERE round_id=? AND user_id=?',
                                  (round_id,user_id)).fetchone()
            conn.execute('INSERT INTO forecasts(round_id,user_id,probability_pct,updated_at) VALUES(?,?,?,?) '
                         'ON CONFLICT(round_id,user_id) DO UPDATE SET probability_pct=excluded.probability_pct, '
                         'updated_at=excluded.updated_at',
                         (round_id,user_id,probability_pct,time.time()))
            return 'updated' if existing else 'created'

    def get_forecast(self,round_id:str,user_id:str)->int|None:
        with self._db() as conn:
            if not conn.execute('SELECT 1 FROM rounds WHERE id=?',(round_id,)).fetchone():
                raise GameError('round not found',404)
            row=conn.execute('SELECT probability_pct FROM forecasts WHERE round_id=? AND user_id=?',
                             (round_id,user_id)).fetchone()
            return int(row['probability_pct']) if row else None

    def player_history(self,user_id:str,limit:int=20)->dict:
        import json
        from backend.forecast import judge_round,forecast_points
        with self._db() as conn:
            rows=conn.execute('SELECT f.round_id,f.probability_pct,r.status,r.result_json '
                              'FROM forecasts f JOIN rounds r ON r.id=f.round_id '
                              'WHERE f.user_id=? ORDER BY r.opened_at DESC,r.id DESC',
                              (user_id,)).fetchall()
        history=[];scored_rounds=0;total_points=0
        for row in rows:
            judge=judge_round(json.loads(row['result_json'])) if row['status']=='PUBLISHED' and row['result_json'] else {'outcome':'pending'}
            points=forecast_points(int(row['probability_pct']),judge['outcome'])
            if points is not None:
                total_points+=points;scored_rounds+=1
            history.append({'round_id':row['round_id'],'forecast_pct':int(row['probability_pct']),
                            'outcome':judge['outcome'],'points':points,'reason':judge.get('reason')})
        return {'total_points':total_points,'scored_rounds':scored_rounds,'submitted_rounds':len(history),'items':history[:limit]}

    def get_sample(self,sample_id:int):
        with self._db() as conn:
            r=conn.execute('SELECT id,label,version FROM samples WHERE id=? AND available=1',
                           (sample_id,)).fetchone()
            if r is None:raise GameError('not an eligible image',404)
            return dict(r)

    def vote_summary(self,round_id:str)->dict:
        """Aggregated public counts; no identities or forecast probabilities leak."""
        with self._db() as conn:
            round_data=conn.execute('SELECT status,closes_at FROM rounds WHERE id=?', (round_id,)).fetchone()
            if round_data is None:raise GameError('round not found',404)
            count=conn.execute('SELECT count(*),count(DISTINCT user_id) FROM picks WHERE round_id=?',
                               (round_id,)).fetchone()
            predictions=conn.execute('SELECT count(*) FROM forecasts WHERE round_id=?',
                                     (round_id,)).fetchone()[0]
            return {'vote_count':int(count[0]), 'voter_count':int(count[1]),
                    'forecast_count':int(predictions),
                    'frozen':round_data['status']!='OPEN' or time.time()>=round_data['closes_at']}

    def claim_round(self,round_id:str)->str|None:
        """Only one worker can move a locked batch into TRAINING.

        Claims do not expire automatically: after a crash, an operator must
        verify the old process is stopped before recovering this round.
        """
        with self._db(True) as conn:
            row=conn.execute('SELECT status FROM rounds WHERE id=?',(round_id,)).fetchone()
            if row is None:raise GameError('round not found',404)
            if row['status']!='LOCKED':return None
            token=secrets.token_hex(24)
            conn.execute('UPDATE rounds SET status=?,worker_token=?,worker_started_at=?,worker_attempts=worker_attempts+1 WHERE id=?',
                         ('TRAINING',token,time.time(),round_id))
            conn.execute('INSERT INTO events(round_id,kind,details,at) VALUES(?,?,?,?)',
                         (round_id,'ROUND_CLAIMED','{}',time.time()))
            return token

    def recover_training_round(self,round_id:str,expected_token:str):
        """Manual recovery ONLY after confirming the previous process is dead."""
        if not expected_token:
            raise GameError('expected owner token is required',422)
        with self._db(True) as conn:
            row=conn.execute('SELECT status,worker_token FROM rounds WHERE id=?',(round_id,)).fetchone()
            if row is None:raise GameError('round not found',404)
            if row['status']!='TRAINING' or row['worker_token']!=expected_token:
                raise GameError('worker claim no longer matches',409)
            conn.execute('UPDATE rounds SET status=?,worker_token=NULL,worker_started_at=NULL WHERE id=?',
                         ('LOCKED',round_id))
            conn.execute('INSERT INTO events(round_id,kind,details,at) VALUES(?,?,?,?)',
                         (round_id,'ROUND_RECOVERED','{}',time.time()))

    def lock_round(self,round_id:str):
        with self._db(True) as conn:
            row=conn.execute('SELECT status FROM rounds WHERE id=?',(round_id,)).fetchone()
            if row is None:raise GameError('round not found',404)
            if row['status']!='OPEN':raise GameError('round is closed',409)
            conn.execute('UPDATE rounds SET status=?,locked_at=? WHERE id=?',('LOCKED',time.time(),round_id))
            conn.execute('INSERT INTO events(round_id,kind,details,at) VALUES(?,?,?,?)',
                         (round_id,'ROUND_LOCKED','{}',time.time()))

    def publish_result(self,round_id:str,result_json:str):
        """Direct publication is disabled: publish must include atomic promotion.

        Call finalize_round with the unique training owner token instead.
        """
        raise GameError('direct publication is disabled; use finalization with worker claim',409)

    def finalize_round(self, round_id:str,result_json:str,next_round_id:str,
                       next_checkpoint:str,next_targets:tuple[int,int],next_seed:int,
                       consumed_ids:list[int],claim_token:str):
        """Publish + create next OPEN round in one SQLite transaction.

        Only the actually promoted arm's images are removed from availability.
        """
        with self._db(True) as conn:
            row=conn.execute('SELECT status,worker_token,opened_at,closes_at FROM rounds WHERE id=?',(round_id,)).fetchone()
            if row is None or row['status']!='TRAINING' or not claim_token or row['worker_token']!=claim_token:
                raise GameError('round must be TRAINING and owned by this worker to finalize',409)
            duration=self._round_seconds(round(row['closes_at']-row['opened_at']))
            now=time.time()
            conn.execute('UPDATE rounds SET status=?,result_json=?,finished_at=? WHERE id=?',
                         ('PUBLISHED',result_json,now,round_id))
            conn.executemany('UPDATE samples SET available=0 WHERE id=?',
                             [(i,) for i in set(consumed_ids)])
            conn.execute('INSERT INTO rounds(id,checkpoint,target_a,target_b,seed,status,opened_at,closes_at) '
                         'VALUES(?,?,?,?,?,?,?,?)',
                         (next_round_id,next_checkpoint,*next_targets,next_seed,'OPEN',now,now+duration))
            conn.execute('INSERT INTO events(round_id,kind,details,at) VALUES(?,?,?,?)',
                         (round_id,'ROUND_PUBLISHED','{}',now))
            conn.execute('INSERT INTO events(round_id,kind,details,at) VALUES(?,?,?,?)',
                         (next_round_id,'ROUND_OPENED','{}',now))

    def samples_page(self,page:int=1,limit:int=48,label:int|None=None,wrong_only:bool=False,
                     predictions:dict|None=None,search:str=''):
        # Page in SQLite so the normal explorer does not load every CIFAR-10
        # candidate into Python on each user request or automatic refresh.
        if wrong_only and predictions is None:
            raise GameError('model predictions are not available',503)
        if page < 1 or not 1 <= limit <= 48:
            raise GameError('invalid pagination',422)
        clauses=['available=1']
        params=[]
        if label is not None:
            clauses.append('label=?');params.append(label)
        if search:
            clauses.append('instr(CAST(id AS TEXT), ?) > 0');params.append(search)
        where=' WHERE '+' AND '.join(clauses)
        with self._db() as conn:
            if not wrong_only:
                total=conn.execute('SELECT count(*) FROM samples'+where, params).fetchone()[0]
                rows=conn.execute('SELECT id,label,version FROM samples'+where+
                                  ' ORDER BY id LIMIT ? OFFSET ?',
                                  [*params,limit,(page-1)*limit]).fetchall()
                return [dict(row) for row in rows],int(total)
            # Wrong-only is checkpoint-dependent and cannot be reduced to
            # class/ID indexes without first joining prediction metadata.
            rows=conn.execute('SELECT id,label,version FROM samples'+where+
                              ' ORDER BY id',params).fetchall()
        filtered=[dict(row) for row in rows if str(row['id']) in predictions and
                  predictions[str(row['id'])]['predicted'] != row['label']]
        total=len(filtered)
        return filtered[(page-1)*limit:page*limit],total
