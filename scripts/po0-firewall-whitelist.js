/*
 * po0 防火墙自动加白（Surge 脚本）
 *
 * GET  /firewall.php  只读状态：{enabled, whitelist[], limit, currentIp}
 * POST /firewall.php  把"当前请求源 IP"加入白名单（占一个坑位）
 * API 无删除能力（DELETE/PUT 405，POST 不接受指定 IP），坑位只能省着用。
 *
 * 策略：
 * - GET 先查，currentIp 已在白名单则跳过 POST（零坑位消耗）。
 * - WiFi/有线：IP 变了就自动 POST（家宽换 IP 场景，正常使用不受影响）。
 * - 蜂窝（主接口 pdp_ip*，CGNAT IP 频繁变化）：自动触发（cron/事件）在
 *   24h 内最多消耗 CELL_CAP 个新坑位，超限后只通知不 POST；
 *   面板手动刷新不受限 —— 你要用的时候点一下面板必定加白。
 * - KV 记账：记录本设备自动加白过的 IP 及来源，面板上蜂窝加的标 📶。
 *
 * argument: tokens=<pgnfw_xxx>,<pgnfw_yyy>  多 token 英文逗号分割。
 * 触发方式：cron(每 2 分钟)、network-changed 事件、面板手动刷新。
 */

var API = "https://console.po0.com/modules/servers/penguin/api/firewall.php";
var STORE_PREFIX = "po0_fw_";
var CELL_CAP = 2; // 24h 内蜂窝自动加白最多消耗的坑位数
var CELL_WINDOW_MS = 24 * 3600 * 1000;

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

function onCellular() {
  try {
    var iface =
      ($network.v4 && $network.v4.primaryInterface) ||
      ($network.v6 && $network.v6.primaryInterface) ||
      "";
    return iface.indexOf("pdp_ip") === 0;
  } catch (e) {
    return false;
  }
}

function isPanelRun() {
  try {
    return $script.type === "generic"; // 面板手动刷新
  } catch (e) {
    return true;
  }
}

function readHistory(key) {
  try {
    var h = JSON.parse($persistentStore.read(key) || "[]");
    var cutoff = Date.now() - CELL_WINDOW_MS;
    return h.filter(function (e) {
      return e.ts > cutoff;
    });
  } catch (e) {
    return [];
  }
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

function ensureWhitelisted(token, index) {
  var kvState = STORE_PREFIX + index;
  var kvHist = STORE_PREFIX + "hist_" + index;
  var cellular = onCellular();
  var panel = isPanelRun();

  return apiCall("GET", token).then(function (st) {
    var ctx = { st: st, kvState: kvState, kvHist: kvHist, cellular: cellular };
    if (st.error || st.enabled === false || st.applied) return ctx;

    // 需要 POST 占新坑位
    var hist = readHistory(kvHist);
    if (cellular && !panel) {
      var cellUsed = hist.filter(function (e) {
        return e.src === "cell";
      }).length;
      if (cellUsed >= CELL_CAP) {
        st.limited = true; // 蜂窝自动加白限频，面板手动刷新可强制
        return ctx;
      }
    }

    return apiCall("POST", token).then(function (st2) {
      st2.posted = true;
      if (st2.applied) {
        hist.push({ ip: st2.currentIp, src: cellular ? "cell" : "fixed", ts: Date.now() });
        $persistentStore.write(JSON.stringify(hist.slice(-10)), kvHist);
      }
      ctx.st = st2;
      return ctx;
    });
  });
}

// 每 token 一行：不含 token，只含白名单/坑位信息；蜂窝加的 IP 标 📶
function describe(index, ctx) {
  var st = ctx.st;
  var head = "#" + (index + 1) + " ";
  if (st.error) return head + "❌ " + st.error;
  if (st.enabled === false) return head + "⚠️ 防火墙未启用";
  if (st.limited)
    return head + "⏸ 蜂窝自动加白已限频(24h内" + CELL_CAP + "个)，点面板可手动加白";
  if (!st.applied) return head + "❌ 加白未生效 " + st.whitelist.length + "/" + st.limit;

  var hist = readHistory(ctx.kvHist);
  var cellIps = {};
  hist.forEach(function (e) {
    if (e.src === "cell") cellIps[e.ip] = true;
  });
  var ips = st.whitelist
    .map(function (ip) {
      return ip + (cellIps[ip] ? " 📶" : "") + (ip === st.currentIp ? " ←" : "");
    })
    .join("\n    ");
  return (
    head + "✅ " + st.whitelist.length + "/" + st.limit + (st.posted ? " (新加白)" : "") + "\n    " + ips
  );
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
  Promise.all(
    tokens.map(function (t, i) {
      return ensureWhitelisted(t, i);
    })
  ).then(function (results) {
    var okCount = 0;
    var exitIp = "?";
    var lines = [];
    var changed = false;
    var anyPosted = false;
    var anyLimited = false;

    for (var i = 0; i < results.length; i++) {
      var st = results[i].st;
      if (st.applied) okCount++;
      if (st.posted) anyPosted = true;
      if (st.limited) anyLimited = true;
      if (st.currentIp) exitIp = st.currentIp;
      lines.push(describe(i, results[i]));

      var state =
        (st.currentIp || "?") + "|" + (st.applied ? "1" : st.limited ? "L" : "0");
      if ($persistentStore.read(results[i].kvState) !== state) {
        $persistentStore.write(state, results[i].kvState);
        changed = true;
      }
    }

    var allOk = okCount === results.length;
    var title =
      "po0 加白 " + okCount + "/" + results.length + " · 出口 " + exitIp + (onCellular() ? " 📶" : "");
    var content = lines.join("\n");

    // 失败/限频/消耗新坑位且状态有变化时才通知，例行检查保持安静
    if (changed && (!allOk || anyPosted || anyLimited)) {
      $notification.post("po0 防火墙加白", title, content);
    }
    finish(title, content, allOk && !anyLimited);
  });
}
