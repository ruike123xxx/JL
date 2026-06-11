/**
 * 影刀「执行 JS 脚本」— 在 Boss 聊天窗口内运行，返回 JSON 字符串。
 * 输出变量建议: chat_extract_json
 */
(function () {
  function text(el) {
    return (el && (el.innerText || el.textContent) || "").trim();
  }

  var conversation = text(document.querySelector(".chat-conversation"))
    || text(document.querySelector("[class*='chat']"))
    || text(document.body);

  var candidateId = "";
  var m = location.href.match(/uid=([^&]+)/i) || location.href.match(/geekId=([^&]+)/i);
  if (m) candidateId = m[1];

  var resumeHint = "unknown";
  if (conversation.indexOf("备注：无附件简历，仅在线简历") >= 0) {
    resumeHint = "online_only";
  } else if (conversation.indexOf("附件简历") >= 0) {
    resumeHint = "has_attachment";
  }

  var lastMessageFrom = "unknown";
  var lines = conversation.split("\n").filter(Boolean);
  var last = lines[lines.length - 1] || "";
  if (/^(候选人|对方|求职者)/.test(last)) lastMessageFrom = "candidate";
  else if (/^(HR|我|招聘方)/.test(last)) lastMessageFrom = "hr";

  return JSON.stringify({
    candidate_id: candidateId || "unknown",
    conversation: conversation,
    resume_hint: resumeHint,
    last_message_from: lastMessageFrom,
  });
})();
