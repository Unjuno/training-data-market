import test from "node:test";
import assert from "node:assert/strict";
import {existsSync} from "node:fs";

async function api(){
  assert.ok(existsSync(new URL("../src/draft.js",import.meta.url)),"draft persistence module exists");
  return import("../src/draft.js");
}
const memory=()=>{let value=null;return {getItem:()=>value,setItem:(key,v)=>{value=v;}};};
test("empty saved picks replace previously saved picks",async()=>{
  const {saveDraft,loadDraft}=await api();const store=memory();
  assert.equal(saveDraft(store,[1],"first"),true);
  assert.equal(saveDraft(store,[],""),true);
  assert.deepEqual(loadDraft(store,[1,2]),{picks:[],reason:""});
});
test("corrupt and null saved values recover safely",async()=>{
  const {loadDraft}=await api();
  for(const raw of ["{bad", "null", "5", '"string"']){
    assert.deepEqual(loadDraft({getItem:()=>raw},[1]),{picks:[],reason:""});
  }
});
test("restoration sanitizes IDs and trims the reason",async()=>{
  const {loadDraft}=await api();
  const result=loadDraft({getItem:()=>JSON.stringify({picks:[1,1,999,2],reason:"x".repeat(500)})},[1,2]);
  assert.deepEqual(result.picks,[1,2]);assert.equal(result.reason.length,400);
});
test("blocked storage is explicit and non-fatal",async()=>{
  const {saveDraft,loadDraft}=await api();
  const store={getItem(){throw Error("blocked");},setItem(){throw Error("blocked");}};
  assert.deepEqual(loadDraft(store,[1]),{picks:[],reason:""});
  assert.equal(saveDraft(store,[1],""),false);
  assert.equal(saveDraft(null,[1],""),false);
});
