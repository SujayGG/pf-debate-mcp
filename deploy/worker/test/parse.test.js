// Layouts copied from real logged-in Tabroom pages (2026-09-27); names replaced so no student data is committed.
import assert from "node:assert/strict";
import { test } from "node:test";
import { judgeSummary, parseEntryRecord, parseJudgePage } from "../hub/parse.js";

const row = (n, side, opp, judges, votes, speaks) => `<tr id="9${n}"> <td class="smallish" data-text="${n}"> Round ${n} </td>
 <td class="centeralign smallish" data-text="1"> <div class='flexrow nospace'> <span class="half grow nospace"> ${side} </span> </div> </td>
 <td class="smallish nospace padleft"> <a class = "plain padvertless hover padleft" href = "/index/tourn/postings/entry_record.mhtml?entry_id=${opp[0]}&tourn_id=1" >vs ${opp[1]}</a> </td>
 <td class="smallish nospace"> ${judges.map((j) => `<div class='judgeheight nowrap full padleft'> ${j} </div>`).join("")} </td>
 <td class="smallish centeralign nospace"> ${votes.map((v) => `<div class='judgeheight nowrap full padleft'> ${v} </div>`).join("")} </td>
 <td class="smallish centeralign nospace"> <div class='judgeheight nowrap full flexrow'> ${speaks.map(([nm, r, p]) => `<span class="half grow flexrow">
   <span class="threefifths smaller leftalign padleft"> ${nm} </span> <span class="fifth grow rightalign padright"> ${r} </span>
   <span class="fifth grow rightalign padright"> ${p} </span> </span>`).join("")} </div> </td> </tr>`;

const ENTRY = `<h4>Round Results</h4><table id="SchoolAB"> <thead> <tr> <th> Round </th> <th> Side/Order </th> <th> Opp </th>
 <th> Judging </th> <th> Result </th> <th> Scores </th> </tr> </thead> <tbody>
 ${row(3, "Aff", [11, "School C Ann &amp; Bo"], ["Lee, Pat", "Ng, Sam", "Diaz, Ana"], ["W", "L", "W"], [["A, X", 1, 29.5], ["B, Y", 2, 29]])}
 ${row(2, "Neg", [12, "School D Cy &amp; Di"], ["Lee, Pat"], ["L"], [["A, X", 3, 28]])}
 </tbody> </table>`;

test("entry record: sides, opponents, panel ballots, speaks", () => {
  const r = parseEntryRecord(ENTRY);
  assert.equal(r.length, 2);
  assert.deepEqual([r[0].label, r[0].side, r[0].result, r[0].ballots], ["Round 3", "Pro", "W", "2-1"]);
  assert.deepEqual(r[0].opponent, { id: 11, code: "School C Ann & Bo" });
  assert.deepEqual(r[0].judges, ["Lee, Pat", "Ng, Sam", "Diaz, Ana"]);
  assert.deepEqual(r[0].speaks[0], { name: "A, X", rank: 1, points: 29.5 });
  assert.deepEqual([r[1].side, r[1].result, r[1].ballots], ["Con", "L", null]);
  assert.equal(parseEntryRecord("<html>Please login</html>"), null);
});

const JUDGE = `<h3 class="normalweight nospace"> Pat Lee </h3> <h6 class="normalweight">SOME HIGH</h6>
 <table id="judgerecord"> <thead> <tr class="yellowrow"> <th>Tournament</th> </tr> </thead> <tbody class="smallish">
 ${[["VPF", "Aff", "2026-09-26"], ["VPF", "Neg", "2026-09-26"], ["VPF", "Aff", "2026-02-01"], ["VLD", "Aff", "2026-09-26"],
    ["VPF", "Neg", "2024-01-01"]].map(([ev, vote, d]) => `<tr> <td class="nospace"> <a>Some Invitational</a> </td>
   <td class="nowrap centeralign"> HS </td> <td class="nowrap"> <span class="hidden">1790420400</span> ${d} </td>
   <td> ${ev} </td> <td class="nospace"> <span class="hidden">3</span> <a> R3 </a> </td> <td> <a> Team A </a> </td>
   <td> <a> Team B </a> </td> <td class="nowrap"> ${vote} </td> <td class="nowrap"> </td> </tr>`).join("")}
 </tbody> </table>`;

test("judge page: name, school, record; summary counts the last year", () => {
  const j = parseJudgePage(JUDGE);
  assert.equal(j.name, "Pat Lee");
  assert.equal(j.school, "SOME HIGH");
  assert.equal(j.record.length, 5);
  assert.deepEqual(j.record[0], { tourn: "Some Invitational", level: "HS", date: "2026-09-26", event: "VPF", round: "R3",
                                  aff: "Team A", neg: "Team B", vote: "Aff" });
  assert.deepEqual(judgeSummary(j.record, Date.parse("2026-09-27")),
    { rounds: 4, pfDecisions: 3, pro: 2, con: 1, tournaments: 1 });
});
