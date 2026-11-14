"""Pure policies for CIFAR-10 data splits, votes and model safety.

All losses and rates are dimensionless. Public holdout must never be
included in training. These policies are application rules, not scientific
confidence intervals.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

CIFAR_TRAIN = 50_000
CIFAR_TEST = 10_000
SPLIT_SIZES = {"initial": 200, "public": 300, "safety": 200, "candidate": 4_300}


def split_ids(labels: Sequence[int], seed: int) -> dict[str, list[int]]:
    """Create mutually disjoint stratified train splits; keep official test separate.

    labels indices 0..49999 are official CIFAR train, 50000..59999 test.
    """
    if len(labels) != CIFAR_TRAIN + CIFAR_TEST:
        raise ValueError("CIFAR-10 label vector must contain 60,000 examples")
    rng = random.Random(seed)
    by_class: dict[int, list[int]] = defaultdict(list)
    for i, y in enumerate(labels[:CIFAR_TRAIN]):
        if not isinstance(y, int) or not (0 <= y < 10):
            raise ValueError("invalid CIFAR-10 class ID")
        by_class[y].append(i)
    if len(by_class) != 10 or any(len(by_class[k]) != 5000 for k in range(10)):
        raise ValueError("expected 5,000 official training examples per class")
    out: dict[str, list[int]] = {name: [] for name in SPLIT_SIZES}
    for k in range(10):
        indices = by_class[k][:]
        rng.shuffle(indices)
        offset = 0
        for key, n in SPLIT_SIZES.items():
            out[key].extend(indices[offset:offset+n])
            offset += n
        assert offset == 5000
    for indices in out.values():
        indices.sort()
    out['test'] = list(range(CIFAR_TRAIN, CIFAR_TRAIN+CIFAR_TEST))
    return out


def weakness_pair(confusion: Sequence[Sequence[int]]) -> tuple[int,int]:
    """Choose the class pair maximizing two directed false-classification rates."""
    if len(confusion) != 10 or any(len(row) != 10 for row in confusion):
        raise ValueError("expected 10x10 confusion matrix")
    counts = [sum(row) for row in confusion]
    if not all(n > 0 for n in counts):
        raise ValueError("every class needs validation support")
    return max(((i,j) for i in range(10) for j in range(i+1,10)),
               key=lambda pair: (confusion[pair[0]][pair[1]]/counts[pair[0]]+
                                 confusion[pair[1]][pair[0]]/counts[pair[1]],
                                 -pair[0],-pair[1]))


def _balanced_sample(classes: Mapping[int,int], excluded: set[int], n: int,
                     rng: random.Random) -> list[int]:
    by_class: dict[int, list[int]] = defaultdict(list)
    for sample_id, label in classes.items():
        if sample_id not in excluded:
            by_class[label].append(sample_id)
    for candidates in by_class.values():
        rng.shuffle(candidates)
    result: list[int] = []
    # Cross-class round-robin whenever possible; then repeat for remaining IDs.
    while len(result) < n and any(by_class.values()):
        for label in sorted(by_class):
            if by_class[label] and len(result) < n:
                result.append(by_class[label].pop())
    if len(result) != n:
        raise ValueError(f"insufficient candidate images: need {n}")
    return result


def assemble_arms(classes: Mapping[int,int], votes: Mapping[int,int], seed: int,
                  batch_size: int=128, max_voted: int=64,
                  per_class_voted_max: int=48) -> dict:
    """Pick disjoint-within-arm samples; arms may share input IDs.

    Vote ties are randomized deterministically by a fixed round seed.
    """
    if len(classes) < batch_size or not classes:
        raise ValueError("insufficient candidate pool")
    if not all(k in classes for k in votes):
        raise ValueError("a voted sample is not an eligible candidate")
    if not (0 <= max_voted <= batch_size) or per_class_voted_max < 1:
        raise ValueError("invalid voting limits")
    rng = random.Random(seed)
    tie_break = {i: rng.random() for i in votes}
    ordered = sorted(votes,key=lambda i:(-votes[i],tie_break[i],i))
    chosen: list[int] = []
    by_class: Counter[int] = Counter()
    for i in ordered:
        if len(chosen)>=max_voted: break
        if votes[i]<=0: continue
        cls=classes[i]
        if by_class[cls] >= per_class_voted_max: continue
        chosen.append(i)
        by_class[cls]+=1
    fill = _balanced_sample(classes,set(chosen),batch_size-len(chosen),rng)
    control = _balanced_sample(classes,set(),batch_size,rng)
    return {"community":chosen+fill,"random":control,
            "voted":chosen,"has_votes":bool(chosen)}


def safe_arm(before: Mapping, after: Mapping,
             max_loss_increase:float=.01,max_recall_drop:float=.05) -> bool:
    try:
        vals=(before['overall_loss'],before['target_loss'],after['overall_loss'],after['target_loss'],
              *before['recall'],*after['recall'])
        if len(before['recall'])!=10 or len(after['recall'])!=10: return False
        if not all(math.isfinite(x) for x in vals): return False
        return (after['overall_loss'] <= before['overall_loss'] + max_loss_increase + 1e-12
            and after['target_loss'] <= before['target_loss'] + 1e-12
            and all(a + max_recall_drop + 1e-12 >= b
                    for a,b in zip(after['recall'],before['recall'])))
    except (KeyError,TypeError,ValueError):return False


def select_promotion(before: Mapping,community: Mapping,control: Mapping) -> str:
    """The community arm is preferred if safe, even when control improves more."""
    if safe_arm(before,community):return 'community'
    if safe_arm(before,control):return 'random'
    return 'rollback'
