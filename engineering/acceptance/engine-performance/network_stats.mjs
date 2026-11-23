import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
const source=new URL('../../network-p2p/src/onlinecoc_p2p/web/transport.js',import.meta.url);
const {WebRtcTransport}=await import('data:text/javascript;base64,'+Buffer.from(await readFile(source)).toString('base64'));
const transport=Object.create(WebRtcTransport.prototype);
let report=new Map();transport.pc={connectionState:'connected',getStats:async()=>report};
let result=await transport.stats();assert.equal(result.rttMs,null);assert.equal(result.bytesSent,null);assert.equal(result.relay,null);
report=new Map([['t',{type:'transport',selectedCandidatePairId:'p'}],['p',{type:'candidate-pair',localCandidateId:'l',remoteCandidateId:'r',currentRoundTripTime:0,bytesSent:123,bytesReceived:456}],
 ['l',{candidateType:'host',address:'PRIVATE-CANDIDATE'}],['r',{candidateType:'relay',address:'PRIVATE-RELAY'}]]);
result=await transport.stats();assert.equal(result.rttMs,0);assert.equal(result.relay,true);
assert.equal(result.bytesSent,123);assert.equal(result.bytesReceived,456);assert.equal(result.retransmittedPackets,null);
assert.ok(!JSON.stringify(result).includes('PRIVATE'));assert.equal(result.discardedPackets,null);
report.delete('t');report.get('p').nominated=true;report.get('p').state='succeeded';report.get('p').currentRoundTripTime=.012;
result=await transport.stats();assert.equal(result.rttMs,12);assert.equal(result.localType,'host');
report.delete('r');result=await transport.stats();assert.equal(result.relay,null);
await writeFile(new URL('network-stats-results.json',import.meta.url),JSON.stringify({cases:4,passed:true,sample:result,
 limitation:'Synthetic browser getStats contract verification. No live WAN/TURN or retransmission measurement.'},null,2));
console.log('4 network stats boundary cases passed');
