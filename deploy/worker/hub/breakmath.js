// "Will I break?" Monte Carlo for power-matched prelims. Pure module: the hub page imports it (the Worker serves
// this file as-is) and node --test runs it.
//
// Model: rounds 1-2 paired at random; from round 3, teams are sorted by wins (random order within a bracket) and
// adjacent teams meet, so odd brackets pull a team up. An odd field gives one team a bye (a win). Every unplayed
// round is a coin flip. The break is the top `breakSize` by wins, ties broken at random: we can't see speaks or
// opponent wins, so this is an estimate and the page says so.

function rng(seed) { // mulberry32
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle(a, rand) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function defaultBreak(field) {
  let b = 2;
  while (b * 2 <= field / 4) b *= 2;
  return b;
}

function binom(n, k) {
  let r = 1;
  for (let i = 1; i <= k; i++) r = (r * (n - k + i)) / i;
  return r;
}

/**
 * field: teams; prelims: prelim rounds; breakSize: teams that clear; done: rounds already played.
 * Live state: `wins` (current wins of every team, length = field) and `me` (my index) give my exact chance.
 * Record only: `myWins` (my wins after `done` rounds) gives my chance from the P(clear | final wins) table.
 */
export function simulate({ field, prelims, breakSize, done = 0, wins = null, me = null, myWins = null,
                           sims = 10000, seed = 1 }) {
  const rand = rng(seed);
  const tally = {}; // final wins -> [teams, cleared]
  let meCleared = 0;
  const idx = Array.from({ length: field }, (_, i) => i);
  for (let s = 0; s < sims; s++) {
    const w = wins ? wins.slice() : new Array(field).fill(0);
    for (let t = wins ? done : 0; t < prelims; t++) {
      const order = shuffle(idx.slice(), rand);
      if (t >= 2) order.sort((a, b) => w[b] - w[a]); // stable: shuffled order breaks ties
      if (order.length % 2) w[order.pop()]++; // bye
      for (let i = 0; i < order.length; i += 2) w[order[i + (rand() < 0.5 ? 0 : 1)]]++;
    }
    const ranked = shuffle(idx.slice(), rand).sort((a, b) => w[b] - w[a]);
    const cleared = new Uint8Array(field);
    for (let i = 0; i < Math.min(breakSize, field); i++) cleared[ranked[i]] = 1;
    for (let i = 0; i < field; i++) {
      const k = w[i];
      (tally[k] ||= [0, 0])[0]++;
      tally[k][1] += cleared[i];
    }
    if (me !== null) meCleared += cleared[me];
  }
  const byWins = {};
  for (const k of Object.keys(tally)) byWins[k] = { n: tally[k][0], p: tally[k][1] / tally[k][0] };
  const ks = Object.keys(byWins).map(Number).sort((a, b) => a - b);
  const safe = ks.find((k) => ks.filter((j) => j >= k).every((j) => byWins[j].p >= 0.95)) ?? null;
  const bubble = ks.filter((k) => byWins[k].p > 0.05 && byWins[k].p < 0.95);

  let myChance = null;
  if (me !== null) myChance = meCleared / sims;
  else if (myWins !== null) {
    const left = Math.max(0, prelims - done);
    const top = ks.length ? ks[ks.length - 1] : 0;
    myChance = 0;
    for (let j = 0; j <= left; j++) {
      const k = myWins + j;
      const p = byWins[k] ? byWins[k].p : k > top ? 1 : 0;
      myChance += (binom(left, j) / 2 ** left) * p;
    }
  }
  return { byWins, safe, bubble, myChance };
}
