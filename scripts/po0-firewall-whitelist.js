/*
 * po0 防火墙自动加白（Surge 脚本）
 *
 * 空 POST /firewall.php 即把"当前请求源 IP"加入该 token 对应机器的白名单，
 * 响应回显 whitelist / currentIp / limit，用于校验是否生效。
 * argument: tokens=<pgnfw_xxx>,<pgnfw_yyy>  多 token 英文逗号分割。
 * 触发方式：cron(每 5 分钟)、network-changed 事件、面板手动刷新。
 */

var API = "https://console.po0.com/modules/servers/penguin/api/firewall.php";
var STORE_KEY = "po0_fw_last_state";

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

function whitelistSelf(token) {
  return new Promise(function (resolve) {
    $httpClient.post(
      {
        url: API,
        headers: {
          Authorization: "Bearer " + token,
          "Content-Type": "application/json",
        },
        timeout: 15,
      },
      function (error, response, body) {
        var tag = token.slice(0, 12) + "…";
        if (error) {
          resolve({ tag: tag, ok: false, detail: String(error) });
          return;
        }
        try {
          var data = JSON.parse(body);
          var applied =
            data.enabled === true &&
            Array.isArray(data.whitelist) &&
            data.whitelist.indexOf(data.currentIp) !== -1;
          resolve({
            tag: tag,
            ok: applied,
            ip: data.currentIp,
            used: Array.isArray(data.whitelist) ? data.whitelist.length : 0,
            limit: data.limit,
            detail: applied
              ? data.whitelist.length + "/" + data.limit
              : data.enabled === false
                ? "防火墙未启用"
                : "未出现在白名单",
          });
        } catch (e) {
          resolve({
            tag: tag,
            ok: false,
            detail: "响应异常: " + String(body).slice(0, 100),
          });
        }
      }
    );
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
  finish("po0 加白：未配置 token", "请在模块参数 tokens 中填入 pgnfw_ token，多个用 , 分割", false);
} else {
  Promise.all(tokens.map(whitelistSelf)).then(function (results) {
    var okCount = 0;
    var exitIp = "?";
    var lines = [];
    for (var i = 0; i < results.length; i++) {
      var r = results[i];
      if (r.ok) okCount++;
      if (r.ip) exitIp = r.ip;
      lines.push((r.ok ? "✅ " : "❌ ") + r.tag + " " + r.detail);
    }
    var allOk = okCount === results.length;
    var title = "po0 加白 " + okCount + "/" + results.length + " · 出口 " + exitIp;
    var content = lines.join("\n");

    // 仅在出口 IP 变化或出现失败时通知，避免每 5 分钟刷屏
    var state = exitIp + "|" + okCount + "/" + results.length;
    var last = $persistentStore.read(STORE_KEY);
    if (state !== last) {
      $persistentStore.write(state, STORE_KEY);
      if (!allOk || (last && last.split("|")[0] !== exitIp)) {
        $notification.post("po0 防火墙加白", title, content);
      }
    }
    finish(title, content, allOk);
  });
}
