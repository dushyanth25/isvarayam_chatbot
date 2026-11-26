/**
 * Isvaryam AI Chat Client
 *
 * Clean messenger-style chat client with:
 * - Bottom-aligned bot & user avatars
 * - Soft grey bot bubbles & ice-blue user bubbles with in-bubble timestamps
 * - XSS-safe textContent rendering for user input & sanitized markdown for bot replies
 * - Last-8-turns conversation history & header menu controls
 */

(function () {
  const chatbox = document.getElementById("chatbox");
  const chatForm = document.getElementById("chatForm");
  const userInput = document.getElementById("userInput");
  const sendButton = document.getElementById("sendButton");
  const typingIndicator = document.getElementById("typingIndicator");
  const quickChips = document.querySelectorAll(".chip");
  const welcomeTime = document.getElementById("welcomeTime");
  const backResetBtn = document.getElementById("backResetBtn");
  const menuBtn = document.getElementById("menuBtn");
  const headerMenu = document.getElementById("headerMenu");
  const menuNewChat = document.getElementById("menuNewChat");

  const conversationHistory = [];
  const MAX_HISTORY_TURNS = 8;
  let isLoading = false;

  const BOT_AVATAR_SVG =
    '<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<circle cx="18" cy="18" r="18" fill="#E9EEF5"/>' +
    '<rect x="8" y="10" width="20" height="16" rx="6" fill="#FFFFFF" stroke="#B8C4D4" stroke-width="1.5"/>' +
    '<rect x="10.5" y="12.5" width="15" height="10" rx="4" fill="#1E293B"/>' +
    '<circle cx="15" cy="17" r="1.5" fill="#FFFFFF"/>' +
    '<circle cx="21" cy="17" r="1.5" fill="#FFFFFF"/>' +
    '<path d="M16 19.5C16.8 20.3 19.2 20.3 20 19.5" stroke="#FFFFFF" stroke-width="1.3" stroke-linecap="round"/>' +
    "</svg>";

  const USER_AVATAR_SVG =
    '<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<circle cx="18" cy="18" r="18" fill="#F1E7DD"/>' +
    '<circle cx="18" cy="14" r="5.5" fill="#C98A63"/>' +
    '<path d="M8.5 30C9.8 24.5 13.5 22 18 22C22.5 22 26.2 24.5 27.5 30" fill="#4B6B8A"/>' +
    "</svg>";

  function formatTime() {
    return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  function scrollToBottom() {
    chatbox.scrollTop = chatbox.scrollHeight;
  }

  function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function renderSafeMarkdown(rawText) {
    if (!rawText) return "";

    const escaped = escapeHTML(rawText);
    const withLinks = escaped.replace(
      /\[([^\]]+)\]\((https:\/\/[a-zA-Z0-9\-_.~:/?#[\]@!$&*+,;=%]+)\)/g,
      (match, label, url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`
    );
    const withBold = withLinks.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    const withItalics = withBold.replace(/(^|[^*])\*([^*]+)\*([^*]|$)/g, "$1<em>$2</em>$3");

    const lines = withItalics.split("\n");
    let inList = false;
    let htmlOutput = "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        if (!inList) {
          htmlOutput += "<ul>";
          inList = true;
        }
        htmlOutput += `<li>${trimmed.substring(2)}</li>`;
      } else {
        if (inList) {
          htmlOutput += "</ul>";
          inList = false;
        }
        if (trimmed) {
          htmlOutput += `<p>${trimmed}</p>`;
        }
      }
    }

    if (inList) {
      htmlOutput += "</ul>";
    }

    return htmlOutput || `<p>${escaped}</p>`;
  }

  function addUserMessage(text) {
    const row = document.createElement("div");
    row.className = "msg-row user";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar user-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.innerHTML = USER_AVATAR_SVG;

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    const content = document.createElement("div");
    content.className = "msg-text";
    content.textContent = text;

    const time = document.createElement("div");
    time.className = "msg-time";
    time.textContent = formatTime();

    bubble.appendChild(content);
    bubble.appendChild(time);
    row.appendChild(avatar);
    row.appendChild(bubble);
    chatbox.appendChild(row);
    scrollToBottom();
  }

  function addBotMessage(text, images) {
    const row = document.createElement("div");
    row.className = "msg-row bot";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar bot-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.innerHTML = BOT_AVATAR_SVG;

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    const content = document.createElement("div");
    content.className = "msg-text";
    content.innerHTML = renderSafeMarkdown(text);

    bubble.appendChild(content);

    if (Array.isArray(images) && images.length > 0) {
      const imgContainer = document.createElement("div");
      imgContainer.className = "product-images";

      images.forEach((imgUrl) => {
        if (typeof imgUrl === "string" && /^https:\/\/[a-zA-Z0-9\-_.~:/?#[\]@!$&*+,;=%]+$/.test(imgUrl)) {
          const imgElem = document.createElement("img");
          imgElem.src = imgUrl;
          imgElem.alt = "Isvaryam Product";
          imgElem.className = "product-img-card";
          imgElem.loading = "lazy";
          imgContainer.appendChild(imgElem);
        }
      });

      if (imgContainer.children.length > 0) {
        bubble.appendChild(imgContainer);
      }
    }

    const time = document.createElement("div");
    time.className = "msg-time";
    time.textContent = formatTime();

    bubble.appendChild(time);
    row.appendChild(avatar);
    row.appendChild(bubble);
    chatbox.appendChild(row);
    scrollToBottom();
  }

  function updateSendButton() {
    sendButton.disabled = isLoading || userInput.value.trim().length === 0;
  }

  function setTyping(typing) {
    isLoading = typing;
    userInput.disabled = typing;
    updateSendButton();

    if (typing) {
      typingIndicator.classList.remove("hidden");
    } else {
      typingIndicator.classList.add("hidden");
      userInput.focus();
    }
    scrollToBottom();
  }

  function resetChat() {
    conversationHistory.length = 0;
    const rows = chatbox.querySelectorAll(".msg-row");
    rows.forEach((row) => {
      if (row.id !== "initialGreeting") {
        row.remove();
      }
    });
    if (welcomeTime) {
      welcomeTime.textContent = formatTime();
    }
    headerMenu.classList.add("hidden");
    menuBtn.setAttribute("aria-expanded", "false");
    userInput.value = "";
    updateSendButton();
    userInput.focus();
  }

  async function handleSendMessage(messageText) {
    const text = (messageText || userInput.value || "").trim();
    if (!text || isLoading) return;

    userInput.value = "";
    updateSendButton();
    addUserMessage(text);

    const historyPayload = conversationHistory.slice(-MAX_HISTORY_TURNS);
    setTyping(true);

    try {
      const response = await fetch("/chatbot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: historyPayload
        })
      });

      const data = await response.json();

      if (response.ok && data.response) {
        addBotMessage(data.response, data.images || []);

        conversationHistory.push({ role: "user", content: text });
        conversationHistory.push({ role: "assistant", content: data.response });

        while (conversationHistory.length > MAX_HISTORY_TURNS) {
          conversationHistory.shift();
        }
      } else {
        const errorText = data.error || data.response || "We could not process your query. Please try again.";
        addBotMessage(errorText);
      }
    } catch (err) {
      console.error("Chatbot request failed:", err);
      addBotMessage("Could not connect to the server. Please check your connection or reach us at +91 9578822000.");
    } finally {
      setTyping(false);
    }
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleSendMessage();
  });

  userInput.addEventListener("input", updateSendButton);

  quickChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const query = chip.getAttribute("data-query");
      if (query) handleSendMessage(query);
    });
  });

  backResetBtn.addEventListener("click", resetChat);
  menuNewChat.addEventListener("click", resetChat);

  menuBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const isHidden = headerMenu.classList.toggle("hidden");
    menuBtn.setAttribute("aria-expanded", String(!isHidden));
  });

  document.addEventListener("click", (e) => {
    if (!headerMenu.classList.contains("hidden") && !headerMenu.contains(e.target) && e.target !== menuBtn) {
      headerMenu.classList.add("hidden");
      menuBtn.setAttribute("aria-expanded", "false");
    }
  });

  window.addEventListener("load", () => {
    if (welcomeTime) {
      welcomeTime.textContent = formatTime();
    }
    updateSendButton();
    userInput.focus();
  });
})();
