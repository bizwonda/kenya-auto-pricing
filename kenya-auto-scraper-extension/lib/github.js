// GitHub integration — uploads scraped data directly to repo and triggers training

const GITHUB_API = "https://api.github.com";

async function getSettings() {
  return chrome.storage.local.get({
    githubToken: "",
    githubRepo: "bizwonda/kenya-auto-pricing",
    githubBranch: "main",
  });
}

async function pushToGitHub(listings) {
  const settings = await getSettings();
  if (!settings.githubToken) {
    throw new Error("GitHub token not configured. Click Settings in the popup.");
  }

  const [owner, repo] = settings.githubRepo.split("/");
  const branch = settings.githubBranch;
  const token = settings.githubToken;

  // 1. Get current commit SHA for the branch
  const branchResp = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/git/ref/heads/${branch}`,
    { headers: { Authorization: `token ${token}` } }
  );
  if (!branchResp.ok) throw new Error(`Branch fetch failed: ${branchResp.status}`);
  const branchData = await branchResp.json();
  const baseSha = branchData.object.sha;

  // 2. Get base tree
  const commitResp = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/git/commits/${baseSha}`,
    { headers: { Authorization: `token ${token}` } }
  );
  const commitData = await commitResp.json();
  const baseTreeSha = commitData.tree.sha;

  // 3. Create new blobs for the data files
  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const jsonContent = JSON.stringify(listings, null, 2);
  const csvHeaders = [
    "source", "make", "model", "year", "mileage_km", "engine_cc",
    "transmission", "price_kes", "price_usd", "location", "url", "scraped_at",
  ];
  const csvContent =
    csvHeaders.join(",") +
    "\n" +
    listings
      .map((l) =>
        csvHeaders
          .map((h) => {
            const v = l[h];
            if (v === null || v === undefined) return "";
            if (typeof v === "string" && v.includes(",")) return `"${v}"`;
            return String(v);
          })
          .join(",")
      )
      .join("\n");

  // Create blobs
  const createBlob = async (content) => {
    const resp = await fetch(
      `${GITHUB_API}/repos/${owner}/${repo}/git/blobs`,
      {
        method: "POST",
        headers: {
          Authorization: `token ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ content: btoa(unescape(encodeURIComponent(content))), encoding: "base64" }),
      }
    );
    if (!resp.ok) throw new Error(`Blob creation failed: ${resp.status}`);
    return (await resp.json()).sha;
  };

  const jsonBlobSha = await createBlob(jsonContent);
  const csvBlobSha = await createBlob(csvContent);

  // 4. Create tree with new files
  const treeResp = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/git/trees`,
    {
      method: "POST",
      headers: {
        Authorization: `token ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        base_tree: baseTreeSha,
        tree: [
          {
            path: `data/listings/scrape_${ts}.json`,
            mode: "100644",
            type: "blob",
            sha: jsonBlobSha,
          },
          {
            path: `data/listings/scrape_${ts}.csv`,
            mode: "100644",
            type: "blob",
            sha: csvBlobSha,
          },
        ],
      }),
    }
  );
  if (!treeResp.ok) throw new Error(`Tree creation failed: ${treeResp.status}`);
  const newTreeSha = (await treeResp.json()).sha;

  // 5. Create commit
  const newCommitResp = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/git/commits`,
    {
      method: "POST",
      headers: {
        Authorization: `token ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: `📊 Scrape upload: ${listings.length} listings — ${ts}`,
        tree: newTreeSha,
        parents: [baseSha],
      }),
    }
  );
  if (!newCommitResp.ok) throw new Error(`Commit failed: ${newCommitResp.status}`);
  const newCommitSha = (await newCommitResp.json()).sha;

  // 6. Update branch ref
  const updateRefResp = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/git/refs/heads/${branch}`,
    {
      method: "PATCH",
      headers: {
        Authorization: `token ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ sha: newCommitSha, force: false }),
    }
  );
  if (!updateRefResp.ok) throw new Error(`Ref update failed: ${updateRefResp.status}`);

  return { commit: newCommitSha, count: listings.length };
}

async function triggerTraining() {
  const settings = await getSettings();
  if (!settings.githubToken) return;

  const [owner, repo] = settings.githubRepo.split("/");
  const token = settings.githubToken;

  // Trigger train workflow via workflow_dispatch
  const resp = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/actions/workflows/train.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `token ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: settings.githubBranch }),
    }
  );

  return resp.ok;
}
