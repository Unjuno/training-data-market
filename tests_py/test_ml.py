import math
import pytest
import torch
import numpy as np
from backend.ml import TinyCNN, train_steps, evaluate, metric_pack

class FixtureData(torch.utils.data.Dataset):
    def __init__(self):
        rg=np.random.default_rng(4)
        self.x=torch.from_numpy(rg.random((160,3,32,32),dtype=np.float32))
        self.y=torch.tensor([i%10 for i in range(160)],dtype=torch.long)
    def __len__(self): return len(self.y)
    def __getitem__(self,i):return self.x[i],self.y[i]


def test_model_runs_true_gradient_steps_and_evaluation():
    d=FixtureData()
    torch.manual_seed(4)
    net=TinyCNN()
    optim=torch.optim.SGD(net.parameters(),lr=0.01,momentum=.9)
    losses,steps=train_steps(net,optim,d,list(range(128)),epochs=2,batch_size=32,seed=11)
    assert len(losses)==8 and steps==8
    assert all(math.isfinite(v) for v in losses)
    metrics=evaluate(net,d,list(range(160)),targets=(3,5),batch_size=64)
    assert math.isfinite(metrics['overall_loss'])
    assert len(metrics['recall'])==10
    assert 0<=metrics['accuracy']<=1
    assert sum(sum(row) for row in metrics['confusion'])==160
    assert metrics['target_loss']>=0


def test_metric_pack_rejects_unsupported_class_pair():
    logits=torch.zeros(10,10)
    labels=torch.arange(10)
    result=metric_pack(logits,labels,targets=(2,7))
    assert result['accuracy']==pytest.approx(.1,abs=1e-7)
    assert result['target_loss']>0


def test_locked_round_trains_both_arms_and_opens_next(monkeypatch,tmp_path):
    from backend.store import GameStore
    from backend import ml
    from backend.ml import atomic_json,atomic_checkpoint
    torch.manual_seed(7)
    state=tmp_path/'state';state.mkdir()
    fake=FixtureData()
    # Dataset contains 160 examples in the original fixture; repeat to 280 examples.
    class SmallCIFAR(torch.utils.data.Dataset):
        def __len__(self):return 480
        def __getitem__(self,i):return fake[i%len(fake)]
    monkeypatch.setattr(ml,'CombinedCIFAR',lambda _:SmallCIFAR())
    db=GameStore(state/'votes.sqlite3');db.initialize()
    db.bootstrap_samples([(i,i%10) for i in range(400)],version='fixture')
    db.open_round('round-0001','initial',(3,5),111)
    db.set_pick('round-0001','alice',3)
    db.lock_round('round-0001')
    model=TinyCNN();opt=torch.optim.SGD(model.parameters(),lr=.01,momentum=.9)
    atomic_checkpoint(state/'checkpoints'/'initial.pt',{'model':model.state_dict(),'optimizer':opt.state_dict(),'seed':6,'steps':0})
    atomic_json(state/'manifest.json',{'splits':{'public':list(range(400,440)),'safety':list(range(440,480))}})
    result=ml.run_locked_round(tmp_path/'missing-data',state,'round-0001')
    assert result['community_steps']==40 and result['random_steps']==40
    assert result['next_round']=='round-0002'
    assert db.get_round('round-0001')['status']=='PUBLISHED'
    assert db.get_round('round-0002')['status']=='OPEN'
    assert (state/'predictions'/(result['next_round']+'.json')).exists()
    assert len(result['selected_ids'])==128
