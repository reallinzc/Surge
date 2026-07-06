/*
 * po0 防火墙自动加白（Surge 脚本）
 *
 * GET  /firewall.php  只读状态：{enabled, whitelist[], limit, currentIp}
 * POST /firewall.php  把"当前请求源 IP"加入白名单（占一个坑位）
 *
 * 策略：先 GET 查状态，currentIp 已在白名单则跳过 POST（避免重复占坑）；
 * 不在时才 POST 并复核。结果写入 $persistentStore（KV），仅在出口 IP
 * 变化或失败时发通知。面板不显示 token，只显示白名单 IP 与坑位占用。
 *
 * argument: tokens=<pgnfw_xxx>,<pgnfw_yyy>  多 token 英文逗号分割。
 * 触发方式：cron(每 5 分钟)、network-changed 事件、面板手动刷新。
 */

var API = "https://console.po0.com/modules/servers/penguin/api/firewall.php";
var STORE_PREFIX = "po0_fw_";

function parseArgument() {
  var out = {};
  if (typeof $argument === "string" && $argument.length > 0) {
    var pairs = $argument.split("&");
    for (var i = 0; i < pairs.length; i++) {
      var idx = pairs[i].indexOf("=");
      if (idx > 0) {
        out[pairs[i].slice(0, idx)] = decodeURIComponent(pairs[i].slice(idx + 1));
      }
    }
  }
  return out;
}

function apiCall(method, token) {
  return new Promise(function (resolve) {
    var fn = method === "POST" ? $httpClient.post : $httpClient.get;
    fn(
      {
        url: API,
        headers: {
          Authorization: "Bearer " + token,
          "Content-Type": "application/json",
        },
        timeout: 15,
      },
      function (error, response, body) {
        if (error) {
          resolve({ error: String(error) });
          return;
        }
        try {
          var data = JSON.parse(body);
          data.applied =
            data.enabled === true &&
            Array.isArray(data.whitelist) &&
            data.whitelist.indexOf(data.currentIp) !== -1;
          resolve(data);
        } catch (e) {
          resolve({ error: "响应异常: " + String(body).slice(0, 80) });
        }
      }
    );
  });
}

// 每 token 一行：不含 token，只含白名单/坑位信息
function describe(index, st) {
  var head = "#" + (index + 1) + " ";
  if (st.error) return head + "❌ " + st.error;
  if (st.enabled === false) return head + "⚠️ 防火墙未启用";
  if (!st.applied) return head + "❌ 加白未生效 " + st.whitelist.length + "/" + st.limit;
  var ips = st.whitelist
    .map(function (ip) {
      return ip === st.currentIp ? ip + " ←" : ip;
    })
    .join("\n    ");
  return head + "✅ " + st.whitelist.length + "/" + st.limit + (st.posted ? " (新加白)" : "") + "\n    " + ips;
}

function ensureWhitelisted(token, index) {
  var kvKey = STORE_PREFIX + index;
  return apiCall("GET", token).then(function (st) {
    if (st.error || st.enabled === false || st.applied) {
      return { st: st, kvKey: kvKey };
    }
    // 当前出口不在白名单，才真正 POST 占一个坑位
    return apiCall("POST", token).then(function (st2) {
      st2.posted = true;
      return { st: st2, kvKey: kvKey };
    });
  });
}

function finish(title, content, allOk) {
  $done({
    title: title,
    content: content,
    icon: allOk ? "checkmark.shield" : "exclamationmark.shield",
    "icon-color": allOk ? "#34C759" : "#FF3B30",
  });
}

var tokens = (parseArgument().tokens || "")
  .split(",")
  .map(function (s) {
    return s.trim();
  })
  .filter(function (s) {
    return s.length > 0;
  });

if (tokens.length === 0) {
  finish("po0 加白：未配置 token", "请在 argument 的 tokens 中填入 pgnfw_ token，多个用 , 分割", false);
} else {
  Promise.all(tokens.map(ensureWhitelisted)).then(function (results) {
    var okCount = 0;
    var exitIp = "?";
    var lines = [];
    var changed = false;
    var anyPosted = false;

    for (var i = 0; i < results.length; i++) {
      var st = results[i].st;
      if (st.applied) okCount++;
      if (st.posted) anyPosted = true;
      if (st.currentIp) exitIp = st.currentIp;
      lines.push(describe(i, st));

      // KV：仅在该 token 的出口 IP / 生效状态变化时更新并标记
      var state = (st.currentIp || "?") + "|" + (st.applied ? "1" : "0");
      if ($persistentStore.read(results[i].kvKey) !== state) {
        $persistentStore.write(state, results[i].kvKey);
        changed = true;
      }
    }

    var allOk = okCount === results.length;
    var title = "po0 加白 " + okCount + "/" + results.length + " · 出口 " + exitIp;
    var content = lines.join("\n");

    // 失败、或消耗了新坑位时才通知；状态无变化的例行检查保持安静
    if (changed && (!allOk || anyPosted)) {
      $notification.post("po0 防火墙加白", title, content);
    }
    finish(title, content, allOk);
  });
}
