/**
 * 影刀「执行 JS 脚本」— 循环外运行一次，抓取左侧候选人列表。
 * 返回 JSON 数组字符串，影刀 json.loads 后供 ForEach 使用。
 * 每项: { index, itemXpath, name, hasUnread }
 *
 * 输出变量建议: web_js_result
 */
(function () {
  function text(el) {
    return ((el && (el.innerText || el.textContent)) || "").trim();
  }

  // Boss直聘聊天页左侧会话列表的常见选择器，从具体到宽泛逐个尝试
  var selectors = [
    ".chat-user-list li",
    "[class*='user-list'] li",
    "[class*='friend'] li",
    "[role='listitem']",
  ];

  var items = [];
  for (var i = 0; i < selectors.length; i++) {
    var found = document.querySelectorAll(selectors[i]);
    if (found.length > 0) {
      items = Array.prototype.slice.call(found);
      break;
    }
  }

  function xpathOf(el) {
    // 生成可复用的绝对 XPath，供影刀「获取元素对象」按 row['itemXpath'] 定位
    var parts = [];
    while (el && el.nodeType === 1 && el !== document.body) {
      var index = 1;
      var sibling = el.previousElementSibling;
      while (sibling) {
        if (sibling.tagName === el.tagName) index++;
        sibling = sibling.previousElementSibling;
      }
      parts.unshift(el.tagName.toLowerCase() + "[" + index + "]");
      el = el.parentElement;
    }
    return "/html/body/" + parts.join("/");
  }

  var result = items.map(function (el, idx) {
    var nameEl =
      el.querySelector("[class*='name']") ||
      el.querySelector("[class*='title']");
    var unreadEl =
      el.querySelector("[class*='badge']") ||
      el.querySelector("[class*='unread']") ||
      el.querySelector("[class*='count']");
    return {
      index: idx,
      itemXpath: xpathOf(el),
      name: text(nameEl) || text(el).split("\n")[0] || "",
      hasUnread: !!(unreadEl && text(unreadEl)),
    };
  });

  return JSON.stringify(result);
})();
