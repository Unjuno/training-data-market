import test from "node:test";
import assert from "node:assert/strict";
import {filterSamples,togglePick,sanitizeSavedPicks} from "../src/selection.js";

const cases=[
  {id:1,classKey:"cat",className:"猫",predictedClass:"犬",loss:1.5,correct:false},
  {id:2,classKey:"dog",className:"犬",predictedClass:"犬",loss:.2,correct:true},
  {id:3,classKey:"cat",className:"猫",predictedClass:"猫",loss:.4,correct:true}
];

test("filters by class / minimum loss / mistakes",()=>{
  assert.deepEqual(filterSamples(cases,{classKey:"cat",wrongOnly:true,minLoss:1}).map(x=>x.id),[1]);
});
test("searches by numeric sample id",()=>{
  assert.deepEqual(filterSamples(cases,{query:"2"}).map(x=>x.id),[2]);
});
test("selection is a capped, unique toggle",()=>{
  assert.deepEqual(togglePick([],1),[1]);
  assert.deepEqual(togglePick([1],1),[]);
  assert.throws(()=>togglePick([1,2],3,2),RangeError);
});
test("restored picks ignore unknown ids and duplicates",()=>{
  assert.deepEqual(sanitizeSavedPicks([1,1,999,3],[1,2,3]),[1,3]);
});

test("ids reject empty, boolean, negative, and non-decimal strings",()=>{
  for(const id of ["", " ", null, true, false, -1, 1.5, "1e3", "0x10", Number.MAX_SAFE_INTEGER+1]) {
    assert.throws(()=>togglePick([],id),TypeError);
  }
});

test("adding an already selected ID is idempotent",async()=>{
  const api=await import("../src/selection.js");
  assert.equal(typeof api.addPick,"function");
  assert.deepEqual(api.addPick([1],"1"),[1]);
  assert.deepEqual(api.addPick([],"2"),[2]);
  assert.deepEqual(api.addPick([1,2],1,2),[1,2]);
  assert.throws(()=>api.addPick([1,2],3,2),RangeError);
});

test("sorting never mutates the original array",()=>{
  const before=structuredClone(cases);
  filterSamples(cases,{sort:"loss"});
  assert.deepEqual(cases,before);
});
