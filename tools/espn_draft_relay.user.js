// ==UserScript==
// @name         ESPN draft room -> local dashboard relay
// @namespace    fantasyfootball.local
// @version      1.3
// @description  Copies every event the ESPN draft room receives to serve.py on this machine, so the dashboard's DRAFTED plan and board follow the draft live. The room keeps its one connection; nothing is sent to ESPN.
// @match        https://fantasy.espn.com/football/draft*
// @run-at       document-start
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @connect      127.0.0.1
// @connect      localhost
// ==/UserScript==

/* WHY THIS EXISTS. ESPN's read API does not show a draft while it is in progress, and the
   draft server that does (fantasydraft.espn.com, Server-Sent Events) allows one connection
   per team -- a second one kicks the browser out with "Duplicate Connection". So instead of
   connecting ourselves we wrap the page's EventSource before the room creates it, and post
   each message to http://127.0.0.1:8000/api/live/relay. serve.py parses SELECTED / SELECTING
   / CLOCK there (live_draft.py, relay mode). Install in Tampermonkey; it only runs on the
   draft-room URL. Change PORT if serve.py is on another port. */
(function () {
  'use strict';
  const PORT = 8000;
  const URL = 'http://127.0.0.1:' + PORT + '/api/live/relay';
  // With any @grant, Tampermonkey runs this in a sandbox whose `window` is a wrapper, so
  // assigning to it never reaches the page. unsafeWindow is the page's real window.
  const W = (typeof unsafeWindow !== 'undefined') ? unsafeWindow : window;
  const NativeES = W.EventSource;
  if (!NativeES) return;

  let sent = 0, failed = 0;
  // Every event carries the league id of the stream it came from, so a tab left open on a
  // finished mock cannot pollute the draft being followed (that happened 2026-09-08).
  const leagueOf = u => { const m = String(u).match(/league-(\d+)|[?&]2=(\d+)/); return m ? (m[1] || m[2]) : ''; };
  function post(text, league) {
    const done = ok => { if (ok) sent++; else failed++; if ((sent + failed) % 50 === 1) console.info('[relay]', sent, 'sent', failed, 'failed'); };
    const headers = {'Content-Type': 'text/plain'};
    if (league) headers['X-Relay-League'] = league;
    if (typeof GM_xmlhttpRequest === 'function') {
      GM_xmlhttpRequest({method: 'POST', url: URL, data: text, headers,
        onload: r => done(r.status >= 200 && r.status < 300), onerror: () => done(false), ontimeout: () => done(false), timeout: 4000});
    } else {
      fetch(URL, {method: 'POST', body: text, headers, keepalive: true})
        .then(r => done(r.ok), () => done(false));
    }
  }

  // The room tries a WebSocket to the same host FIRST (wss://fantasydraft.espn.com/.../JOIN)
  // and falls back to EventSource when that fails -- seen in a mock 2026-09-08. Wrap both;
  // frames on either carry the same text grammar (SELECTED, SELECTING, CLOCK ...).
  const NativeWS = W.WebSocket;
  if (NativeWS) {
    function WrappedWS(url, protocols) {
      const ws = protocols === undefined ? new NativeWS(url) : new NativeWS(url, protocols);
      const u = String(url);
      if (u.includes('fantasydraft.espn.com')) {
        const lg = leagueOf(u);
        console.info('[relay] draft websocket opened, forwarding to', URL, 'league', lg);
        post('JOIN ' + u, lg);
        ws.addEventListener('message', ev => {
          const d = ev.data;
          if (typeof d === 'string') post(d, lg);
          else if (d instanceof Blob) d.text().then(t => post(t, lg));
          else if (d instanceof ArrayBuffer) post(new TextDecoder().decode(d), lg);
        });
        ws.addEventListener('close', () => post('RELAY_ERROR websocket closed', lg));
      }
      return ws;
    }
    WrappedWS.prototype = NativeWS.prototype;
    ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'].forEach(k => WrappedWS[k] = NativeWS[k]);
    W.WebSocket = WrappedWS;
  }

  function Wrapped(url, cfg) {
    const es = cfg === undefined ? new NativeES(url) : new NativeES(url, cfg);
    const u = String(url);
    if (u.includes('fantasydraft.espn.com')) {
      const lg = leagueOf(u);
      console.info('[relay] draft stream opened, forwarding to', URL, 'league', lg);
      post('JOIN ' + u, lg);
      es.addEventListener('message', ev => { if (typeof ev.data === 'string') post(ev.data, lg); });
      es.addEventListener('error', () => post('RELAY_ERROR stream error or reconnect', lg));
    }
    return es;
  }
  Wrapped.prototype = NativeES.prototype;
  Wrapped.CONNECTING = NativeES.CONNECTING; Wrapped.OPEN = NativeES.OPEN; Wrapped.CLOSED = NativeES.CLOSED;
  W.EventSource = Wrapped;
  console.info('[relay] v1.3: WebSocket and EventSource wrapped on the page window; waiting for the draft room to connect');
})();
