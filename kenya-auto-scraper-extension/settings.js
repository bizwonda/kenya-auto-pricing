// Settings page logic

const el = (id) => document.getElementById(id);

// Load current settings
chrome.storage.local.get(
  { githubToken: "", githubRepo: "bizwonda/kenya-auto-pricing", githubBranch: "main" },
  (data) => {
    el("token").value = data.githubToken;
    el("repo").value = data.githubRepo;
    el("branch").value = data.githubBranch;
  }
);

// Save
el("saveBtn").addEventListener("click", () => {
  const token = el("token").value.trim();
  const repo = el("repo").value.trim() || "bizwonda/kenya-auto-pricing";
  const branch = el("branch").value.trim() || "main";

  chrome.storage.local.set(
    { githubToken: token, githubRepo: repo, githubBranch: branch },
    () => {
      el("status").textContent = "✅ Settings saved";
      el("status").className = "good";
    }
  );
});

// Test connection
el("testBtn").addEventListener("click", async () => {
  const token = el("token").value.trim();
  const repo = el("repo").value.trim() || "bizwonda/kenya-auto-pricing";

  if (!token) {
    el("status").textContent = "Enter a token first";
    el("status").className = "error";
    return;
  }

  el("status").textContent = "Testing...";
  el("status").className = "";

  try {
    const [owner, repoName] = repo.split("/");
    const resp = await fetch(
      `https://api.github.com/repos/${owner}/${repoName}`,
      { headers: { Authorization: `token ${token}` } }
    );

    if (resp.ok) {
      const data = await resp.json();
      el(
        "status"
      ).textContent = `✅ Connected! Repo: ${data.full_name} (${data.private ? "private" : "public"})`;
      el("status").className = "good";
    } else if (resp.status === 401) {
      el("status").textContent = "❌ Invalid token";
      el("status").className = "error";
    } else if (resp.status === 404) {
      el("status").textContent = "❌ Repo not found";
      el("status").className = "error";
    } else {
      el("status").textContent = `❌ Error: HTTP ${resp.status}`;
      el("status").className = "error";
    }
  } catch (e) {
    el("status").textContent = `❌ Network error: ${e.message}`;
    el("status").className = "error";
  }
});
