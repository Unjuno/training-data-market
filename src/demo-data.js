/** DEMONSTRATION DATA ONLY. Not sourced from CIFAR-10 or trained model outputs. */
const classes = [
  ["airplane", "飛行機", "✈️"],
  ["automobile", "自動車", "🚗"],
  ["bird", "鳥", "🐦"],
  ["cat", "猫", "🐈"],
  ["deer", "鹿", "🦌"],
  ["dog", "犬", "🐕"],
  ["frog", "カエル", "🐸"],
  ["horse", "馬", "🐎"],
  ["ship", "船", "🚢"],
  ["truck", "トラック", "🚚"]
];

export const CLASS_OPTIONS = classes.map(([key,label])=>({key,label}));

const values = [
  ["cat", "dog", 2.03], ["dog", "cat", 1.81], ["bird", "airplane", 1.52],
  ["cat", "cat", .41], ["dog", "dog", .30], ["deer", "horse", 1.38],
  ["automobile", "truck", 1.05], ["truck", "truck", .22], ["frog", "frog", .28],
  ["bird", "bird", .34], ["horse", "deer", 1.46], ["ship", "airplane", 1.14],
  ["airplane", "airplane", .39], ["automobile", "automobile", .46],
  ["dog", "deer", 1.61], ["cat", "dog", 1.74], ["deer", "deer", .52],
  ["ship", "ship", .19], ["truck", "automobile", .99], ["frog", "bird", 1.12],
  ["horse", "horse", .33], ["dog", "dog", .77], ["cat", "cat", .61],
  ["bird", "bird", .57], ["airplane", "ship", 1.23], ["frog", "frog", .44],
  ["automobile", "truck", 1.32], ["deer", "horse", 1.64], ["ship", "ship", .49],
  ["truck", "truck", .35]
];

const byKey = Object.fromEntries(classes.map(([key,label,emoji])=>[key,{label,emoji}]));

export const DEMO_SAMPLES = values.map(([classKey,predKey,loss],i)=>({
  id:1001+i,
  classKey,
  className:byKey[classKey].label,
  emoji:byKey[classKey].emoji,
  predictedClass:byKey[predKey].label,
  loss,
  correct:classKey===predKey
}));
