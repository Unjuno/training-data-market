"""End-to-end API and real CPU gradients with synthetic, non-CIFAR images."""
from pathlib import Path
import json
from fastapi.testclient import TestClient
from backend import ml
from backend.service import make_app
import torch
from backend.store import GameStore

class FakeImages(torch.utils.data.Dataset):
    def __init__(self):
        self.labels=[i%10 for i in range(480)]
        generator=torch.Generator().manual_seed(52)
        self.x=torch.rand((480,3,32,32),generator=generator)*.08
        for i,j in enumerate(self.labels):
            self.x[i,j%3,4+j%5:15+j%5,5:25]+=.75
        self.x.clamp_(0,1)
    def __len__(self):return len(self.labels)
    def __getitem__(self,i):return self.x[i],self.labels[i]

def init_state(root,fake):
    db=GameStore(root/'votes.sqlite3');db.initialize()
    db.bootstrap_samples([(i,i%10) for i in range(400)],'synthetic-test-only')
    db.open_round('round-0001','initial',(3,5),42)
    net=ml.TinyCNN();opt=torch.optim.SGD(net.parameters(),lr=.01,momentum=.9)
    _,steps=ml.train_steps(net,opt,fake,list(range(80)),epochs=2,batch_size=32,seed=22)
    ml.atomic_checkpoint(root/'checkpoints'/'initial.pt',{'model':net.state_dict(),'optimizer':opt.state_dict(),'seed':22,'steps':steps})
    pub=ml.evaluate(net,fake,list(range(400,440)),(3,5))
    ml.atomic_json(root/'metrics'/'initial.json',{'checkpoint':'initial','target_pair':[3,5],'public':pub})
    ml.atomic_json(root/'predictions'/'initial.json',{'checkpoint':'initial','samples':ml.candidate_predictions(net,fake,list(range(400)))})
    ml.atomic_json(root/'manifest.json',{'dataset':'synthetic-test-only','splits':{'public':list(range(400,440)),'safety':list(range(440,480))}})
    return db

def test_vote_to_train_and_new_round(tmp_path, monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','s'*64)
    monkeypatch.setenv('TDM_ADMIN_KEY','super-secret-'*4)
    monkeypatch.setenv('TDM_PUBLISH_IMAGES','false')
    ml.seed_all(10)
    fake=FakeImages()
    monkeypatch.setattr(ml,'CombinedCIFAR',lambda _:fake)
    db=init_state(tmp_path,fake)
    app=make_app(db,tmp_path)
    with TestClient(app) as alice, TestClient(app) as bob:
        current=alice.get('/v1/rounds/current').json()
        assert current['mode']=='LIVE'
        assert current['metrics']['public']['overall_loss']>0
        assert alice.get('/').status_code==200
        assert alice.get('/live.js').status_code==200
        assert alice.get('/v1/samples?limit=12').json()['total']==400
        assert alice.put('/v1/rounds/round-0001/picks/0').status_code==200
        assert bob.put('/v1/rounds/round-0001/picks/0').status_code==200
        assert alice.get('/v1/rounds/round-0001/picks/me').json()['ids']==[0]
        assert bob.get('/v1/rounds/round-0001/picks/me').json()['ids']==[0]
        assert alice.get('/v1/samples?limit=12').json()['items'][0]['votes']==2
        assert alice.put('/v1/rounds/round-0001/note',json={'text':'この画像が役立つ'}).status_code==200
        assert alice.get('/v1/rounds/round-0001/picks/me').json()['note']=='この画像が役立つ'
        assert alice.post('/v1/admin/rounds/round-0001/lock').status_code==403
        assert alice.post('/v1/admin/rounds/round-0001/lock',headers={'X-Admin-Key':'super-secret-'*4}).status_code==409
        db.lock_round('round-0001')
        assert bob.put('/v1/rounds/round-0001/picks/1').status_code==409
        out=ml.run_locked_round(Path('/synthetic-fixture'),tmp_path,'round-0001')
        assert out['community_steps']==out['random_steps']==40
        assert out['voted_count']==1
        assert out['voted_ids']==[0]
        personal=alice.get('/v1/rounds/round-0001/participation/me').json()
        assert personal['adopted_ids']==[0]
        assert personal['recommended_count']==personal['adopted_count']==1
        assert out['next_round']=='round-0002'
        assert out['promotion'] in ('community','random','rollback')
        assert db.get_round('round-0001')['status']=='PUBLISHED'
        assert db.get_round('round-0002')['status']=='OPEN'
        assert alice.get('/v1/rounds/round-0001/results').json()['results']['promotion']==out['promotion']
        assert alice.get('/v1/rounds/current').json()['round']['id']=='round-0002'
        assert alice.get('/v1/samples').json()['total']>=272
        print(json.dumps({'next_round':out['next_round'],'promotion':out['promotion'],'steps':40},ensure_ascii=False))
