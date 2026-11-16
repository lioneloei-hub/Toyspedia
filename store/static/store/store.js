// Front-end for the two features on the catalog page.
// Plain JavaScript, no framework. Text is always set with textContent (never innerHTML),
// so a customer's message can't inject HTML into the page.

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : "";
}

// ================= Feature 1: Chatbot =================

(function setupChatbot() {
  const root = document.getElementById("assistant");
  if (!root) return;

  const chatUrl = root.dataset.chatUrl;
  const chatBox = document.getElementById("chat");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");

  // The server forgets everything between requests (HTTP is stateless),
  // so the BROWSER keeps the conversation and sends all of it each time.
  const messages = [];

  function addBubble(role, text) {
    const bubble = document.createElement("div");
    bubble.className = `bubble ${role}`;
    bubble.textContent = text;
    chatBox.appendChild(bubble);
    chatBox.scrollTop = chatBox.scrollHeight;
    return bubble;
  }

  addBubble("assistant", "Hi! Ask me about our LEGO, Gunpla, Pokemon cards, Nintendo Switch 1 and 2, etc!");

  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    addBubble("user", text);
    messages.push({ role: "user", content: text });

    const typing = addBubble("assistant typing", "typing…");
    chatForm.querySelector("button").disabled = true;

    try {
      const res = await fetch(chatUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ messages }),
      });
      const data = await res.json();
      typing.remove();

      if (!res.ok) {
        // fetch() doesn't throw on 400/502, so check res.ok ourselves
        addBubble("error", data.error || "Something went wrong.");
        messages.pop(); // forget the message that failed
        return;
      }

      addBubble("assistant", data.reply);
      messages.push({ role: "assistant", content: data.reply });
    } catch (err) {
      typing.remove();
      addBubble("error", "Can't reach the server. Please try again.");
      messages.pop();
    } finally {
      chatForm.querySelector("button").disabled = false;
    }
  });
})();

// ================= Feature 2: Image search =================

(function setupImageSearch() {
  const root = document.getElementById("image-search");
  if (!root) return;

  const searchUrl = root.dataset.searchUrl;
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  const preview = document.getElementById("preview");
  const statusText = document.getElementById("search-status");
  const resultsBox = document.getElementById("results");

  // Show the chosen photo before uploading it
  searchInput.addEventListener("change", () => {
    const file = searchInput.files[0];
    if (file) {
      preview.src = URL.createObjectURL(file);
      preview.hidden = false;
    }
  });

  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = searchInput.files[0];
    if (!file) return;

    // A file isn't JSON, so we send it as FormData (multipart/form-data)
    const formData = new FormData();
    formData.append("image", file);

    statusText.textContent = "Searching…";
    resultsBox.innerHTML = "";
    searchForm.querySelector("button").disabled = true;

    try {
      const res = await fetch(searchUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken() },
        body: formData,
      });
      const data = await res.json();

      if (!res.ok) {
        statusText.textContent = data.error || "Something went wrong.";
        return;
      }

      statusText.textContent = data.results.length ? "Closest matches in our shop:" : "No matches found.";
      for (const match of data.results) {
        const item = document.createElement("div");
        item.className = "result";

        const link = document.createElement("a");
        link.href = match.url;

        const img = document.createElement("img");
        img.src = match.image_url;
        img.alt = match.name;
        link.appendChild(img);

        const name = document.createElement("a");
        name.href = match.url;
        name.textContent = match.name;

        const info = document.createElement("span");
        // Similarity is "how alike the photos look", not a probability.
        info.textContent = `Match ${(match.similarity * 100).toFixed(1)}% · ${match.price} · stock ${match.stock}`;

        item.append(link, name, info);
        resultsBox.appendChild(item);
      }
    } catch (err) {
      statusText.textContent = "Can't reach the server. Please try again.";
    } finally {
      searchForm.querySelector("button").disabled = false;
    }
  });
})();
