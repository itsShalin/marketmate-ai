// Application adapter around the unmodified Meterless H-MEM reference.
import fs from 'node:fs';
import { HMEM } from '../vendor/hmem/reference/src/index.ts';
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const h = new HMEM({persistDir: input.directory, actor: 'marketmate'});
let result: any;
if (input.action === 'remember') {
  const {key, content, source = 'owner'} = input;
  const existing = h.store.all().filter(m => m.tags.includes(`key:${key}`) && !m.supersededBy);
  const prior = existing[existing.length - 1];
  if (source === 'backend_profile' && existing.some(m => m.source === 'owner')) {
    result = {skipped: true, reason: 'owner preference takes priority'};
  } else if (prior?.content === content && prior?.source === source) {
    result = {memory: prior, duplicate: true};
  } else {
    const memory = h.add({content, type: 'preference', layer: source === 'owner' ? 'long_term' : 'working',
      tags: [`key:${key}`, 'marketing', 'brand', 'preferences'], confidence: source === 'owner' ? 1 : 0.8,
      source, provenance: {origin: source === 'owner' ? 'manual' : 'document', learnedAt: Date.now(), label: key},
      supersedes: prior?.id});
    for (const old of existing) {
      h.ledger.log(old.id, 'conflict_detected', 'marketmate', {details: {replacement: memory.id, key}});
      h.store.update(old.id, {supersededBy: memory.id});
      h.ledger.log(old.id, 'conflict_resolved', 'marketmate', {details: {strategy: 'explicit_key_replacement', replacement: memory.id}});
    }
    result = {memory};
  }
} else if (input.action === 'recall') {
  const relevant = h.query(input.query);
  // Stable business preferences apply even when a short request shares no tokens.
  // This is an application policy, separate from H-MEM's canonical ranking.
  const pinned = h.store.all().filter(m => m.type === 'preference' && !m.supersededBy && !m.tags.includes('review'));
  pinned.sort((a,b) => b.timestamp-a.timestamp || b.id.localeCompare(a.id));
  const chosen = pinned.slice(0,5).map(memory => ({memory, relevance: h.retrieval.scoreOne(memory, input.query)}));
  for (const item of relevant.memories) {
    if (chosen.length < 5 && !chosen.some(x => x.memory.id === item.memory.id) && !item.memory.supersededBy && !item.memory.tags.includes('review')) chosen.push(item);
  }
  const read = new Set(relevant.memories.map(x=>x.memory.id));
  for (const {memory} of chosen) if (!read.has(memory.id)) {
    h.store.touch(memory.id);
    h.ledger.log(memory.id, 'read', 'marketmate', {details: {query: input.query, reason: 'active business preference'}});
  }
  h.store.persist();
  result = {context: h.retrieval.formatReinjection(chosen), memories: chosen.map(({memory, relevance})=>({id:memory.id,content:memory.content,source:memory.source,layer:memory.layer,confidence:memory.confidence,relevance})),
    trace: {...relevant.trace, applicationPolicy: 'include up to five active business preferences', selectedIds: chosen.map(x=>x.memory.id)}};
} else if (input.action === 'inspect') {
  result = {memories: h.store.all().map(({embedding,...m})=>m), ledger: h.ledger.all()};
} else if (input.action === 'feedback') {
  h.feedback(input.memory_id, input.kind); result = {ok:true};
} else throw new Error('Unknown memory action');
process.stdout.write(JSON.stringify(result));
