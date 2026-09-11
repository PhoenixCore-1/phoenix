/* Phoenix User UI V0.1 — Core AI workspace. */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizeResult(response) {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.results)) return response.results;
  if (Array.isArray(response?.items)) return response.items;
  return [];
}

export function renderAIWorkspace({ workspaceView, coreServiceAdapter }) {
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">Phoenix Core</p>
        <h1 class="workspace-title">AI Assistant</h1>
        <p class="workspace-subtitle">Use the Phoenix AI service through the Core service boundary.</p>
      </div>
    </header>
    <section class="card panel ai-workspace">
      <form class="ai-form" data-ai-form>
        <label for="ai-prompt"><strong>Ask Phoenix AI</strong></label>
        <div class="ai-input-row">
          <textarea id="ai-prompt" name="prompt" rows="4" maxlength="4000" placeholder="Ask a question or request assistance..."></textarea>
          <button class="button primary" type="submit">Ask AI</button>
        </div>
      </form>
      <div class="status" data-ai-status role="status" aria-live="polite">Ready. Requests are sent through the Core AI service boundary.</div>
      <section class="ai-response" data-ai-response aria-live="polite" hidden></section>
    </section>
  `;

  const form = workspaceView.querySelector("[data-ai-form]");
  const promptInput = workspaceView.querySelector("#ai-prompt");
  const status = workspaceView.querySelector("[data-ai-status]");
  const responseView = workspaceView.querySelector("[data-ai-response]");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const prompt = promptInput.value.trim();
    if (!prompt) {
      status.className = "status error";
      status.textContent = "Enter a question or request before asking AI.";
      promptInput.focus();
      return;
    }

    form.querySelector("button[type='submit']").disabled = true;
    status.className = "status loading";
    status.textContent = "Connecting to Phoenix AI...";
    responseView.hidden = true;
    responseView.replaceChildren();

    try {
      const response = await coreServiceAdapter.openAIWorkspace({ prompt });
      const results = normalizeResult(response);
      const answer = response?.answer ?? response?.message ?? response?.text;

      if (!answer && results.length === 0) {
        throw new Error("Phoenix AI returned no usable response.");
      }

      status.className = "status success";
      status.textContent = "Phoenix AI response received.";
      responseView.hidden = false;
      responseView.innerHTML = answer
        ? `<div class="ai-answer">${escapeHtml(answer).replaceAll("\n", "<br>")}</div>`
        : results.map((item) => `<article class="ai-result"><strong>${escapeHtml(item.title || item.type || "AI result")}</strong><div>${escapeHtml(item.description || item.content || item.text || "")}</div></article>`).join("");
    } catch (error) {
      status.className = "status error";
      status.textContent = error?.message || "Phoenix AI is currently unavailable.";
      responseView.hidden = true;
    } finally {
      form.querySelector("button[type='submit']").disabled = false;
    }
  });
}
