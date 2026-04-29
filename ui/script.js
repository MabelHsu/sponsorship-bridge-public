const $ = (id) => document.getElementById(id);
let mode = "brand";
let lastRun = null; // {kind:"preview"|"live", mode:"brand"|"creator"} — for refinement re-fire

const scenarios = {
    brand: [
        { label: "Eco skincare", name: "EcoGlow Skincare", brief: "Eco-friendly skincare targeting women 18-35 in the US. Looking for creators in skincare, clean beauty, vegan beauty, or sustainable lifestyle." },
        { label: "Fitness supplements", name: "FitLife Supplements", brief: "Fitness supplement brand targeting men and women 18-30 in Southeast Asia. Gym training, workout routines, nutrition, and healthy lifestyle creators." },
        { label: "Sustainable home", name: "GreenHome Co.", brief: "Launching sustainable home products for eco-conscious adults 25-45. Zero-waste living, home organization, sustainable swaps, minimalist lifestyle." },
    ],
    creator: [
        { label: "Sustainable lifestyle", name: "Gittemary Johansen Eco creator", brief: "I'm a creator. My channel https://www.youtube.com/channel/UCFQ_CWYmt-ScWaPX4YfnBrQ covers sustainable living and zero-waste lifestyle. What brands in your database would be a good match for me?" },
        { label: "Skincare creator", name: "NaturalSkinVlog", brief: "Skincare YouTube creator, 95K subscribers. Natural skincare, sensitive skin, ingredient education, gentle wellness, US audience." },
        { label: "Productivity tech", name: "DeskFlow Reviews", brief: "Tech and productivity creator, 120K subscribers. Desk setups, productivity software, keyboards, gadgets, remote-work tools." },
    ],
};

// Signal palette for the ribbon — distinct hues per signal, all muted to match the editorial palette
const SIGNAL_COLORS = {
    engagement: "#a7563a", audience: "#b8883c", relevance: "#7a6a3d",
    geography: "#567052", activity: "#2d5f48", maturity: "#456b6b",
    recency: "#4a5f7e", quality: "#6b4a6b",
};

// ── helpers ──────────────────────────────────────────────
const compact = (n) => {
    n = Number(n || 0);
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(".0", "") + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1).replace(".0", "") + "K";
    return String(n);
};
const esc = (t) => String(t || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const linkify = (t) => {
    let h = esc(t);
    h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
    h = h.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noreferrer">$2</a>');
    return h;
};
const ARROW = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>';
const EXT = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>';
const MAIL = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>';
const CAL = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>';
const PLUS = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>';

function initialsFor(name) {
    const parts = String(name || "").trim().split(/\s+/);
    if (!parts[0]) return "?";
    if (parts.length === 1) return parts[0][0].toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// ── ribbon (signature element) ───────────────────────────
function ribbonHtml(components, opts) {
    opts = opts || {};
    if (!Array.isArray(components) || !components.length) return "";
    const earned = components.reduce((s, c) => s + Number(c.points || 0), 0);
    const bands = components.map((c) => {
        const w = Number(c.points || 0) / 100 * 100; // percent of full 100
        const col = SIGNAL_COLORS[c.key] || "#6b5d4f";
        return `<div class="seg-band" style="width:${w.toFixed(2)}%;background:${col}" title="${esc(c.label)}: ${c.points}/${c.max}"></div>`;
    }).join("");
    const remaining = Math.max(0, 100 - earned);
    const missed = remaining > 0 ? `<div class="seg-band" style="width:${remaining.toFixed(2)}%;background:transparent"></div>` : "";
    if (opts.mini) return `<div class="mini-ribbon">${bands}${missed}</div>`;
    const legend = components.map((c) => {
        const col = SIGNAL_COLORS[c.key] || "#6b5d4f";
        return `<div class="leg"><span class="swatch" style="background:${col}"></span><span class="lbl">${esc(c.label)}</span><span class="val">${Number(c.points).toFixed(1)}/${c.max}</span></div>`;
    }).join("");
    return `
    <div class="ribbon-wrap">
      <div class="ribbon-title">
        <span>Signal ribbon — eight weighted components</span>
        <span class="note">Total ${earned.toFixed(1)} of 100 earned</span>
      </div>
      <div class="ribbon">${bands}${missed}</div>
      <div class="ribbon-legend">${legend}</div>
    </div>`;
}

// ── Brand Mode: creator shortlist ────────────────────────
function renderCreatorShortlist(matches, brandName, brandBrief) {
    const out = $("results");
    if (!matches.length) {
        out.innerHTML = `<div class="empty"><h2>No viable matches.</h2><p>Try broadening the brief or switching scenarios.</p></div>`;
        return;
    }
    const [top, ...rest] = matches;
    const chUrl = (m) => m.channel_url || `https://www.youtube.com/results?search_query=${encodeURIComponent(m.creator_name + " YouTube channel")}`;
    const topicTags = (txt) => (txt || "").split(",").map(s => s.trim()).filter(Boolean).slice(0, 4).map(t => `<span class="tag">${esc(t)}</span>`).join("");

    const brandSummary = `
    <div class="panel left">
      <div class="p-eyebrow">Your brief · Brand</div>
      <div class="p-title">${esc(brandName || "—")}</div>
      <div class="p-body">${esc(brandBrief || "—")}</div>
    </div>`;

    const creatorSummary = `
    <div class="panel right">
      <div class="p-eyebrow">Recommended match · Creator</div>
      <div class="p-title">${esc(top.creator_name)}</div>
      <div class="p-body">${esc(top.content_topics ? `Channel topics: ${top.content_topics}.` : "")}</div>
      <div class="tags">${topicTags(top.content_topics)}</div>
    </div>`;

    const pct = Math.round(Number(top.fit_score || 0));
    const videoList = (top.recent_videos || []).slice(0, 3).map((v, i) =>
        `<a href="${v.url}" target="_blank" rel="noreferrer"><span>${esc(v.title || ("Recent video " + (i + 1)))}</span><span class="ext">youtube.com</span></a>`
    ).join("");

    const hero = `
    <article class="match">
      <div class="match-header">
        <div>
          <div class="m-kicker">Recommended · ${esc(top.confidence || "medium")} confidence</div>
          <h2><a href="${chUrl(top)}" target="_blank" rel="noreferrer">${esc(top.creator_name)}</a></h2>
          <div class="stats"><strong>${compact(top.subscribers)}</strong> subscribers &nbsp;·&nbsp; ${esc(top.country || "Unknown")} &nbsp;·&nbsp; ${esc(top.engagement_rate)} engagement (${esc(top.engagement_rating || "—")})</div>
        </div>
      </div>
      <div class="split">
        ${brandSummary}
        <div class="seam">
          <div class="numeral">${pct}<sup>/100</sup></div>
          <div class="label">Fit</div>
          <div class="conf">${esc(top.confidence || "medium")} confidence</div>
        </div>
        ${creatorSummary}
      </div>
      ${ribbonHtml(top.score_components)}
      <p class="reasoning">${esc(top.reasoning || "")}</p>
      ${(top.risk_flags && top.risk_flags.length) ? `<div class="risks"><strong>Risks</strong>${esc(top.risk_flags.join(" · "))}</div>` : ""}
      ${videoList ? `<div class="refs"><div class="refs-lbl">Recent videos</div><div class="refs-list">${videoList}</div></div>` : ""}
      <div class="actions">
        <a class="primary" href="${chUrl(top)}" target="_blank" rel="noreferrer">${EXT}Open channel</a>
        <a href="#" data-sched-creator="${esc(top.creator_name)}">${CAL}Schedule intro call</a>
        <a href="#" data-outreach-creator="${esc(top.creator_name)}" data-outreach-topics="${esc(top.content_topics||"")}" data-outreach-titles="${esc((top.recent_videos||[]).slice(0,5).map(v=>v.title).join(", "))}" data-outreach-reasoning="${esc(top.reasoning||"")}">${MAIL}Draft outreach</a>
        <a href="#" data-add-dossier="${esc(JSON.stringify({type:'creator', id:top.channel_id, name:top.creator_name, data:top}))}">${PLUS}Add to Dossier</a>
      </div>
    </article>`;

    const runners = rest.slice(0, 2).map((m, i) => {
        const pct2 = Math.round(Number(m.fit_score || 0));
        const ch2 = chUrl(m);
        return `
      <article class="card">
        <div class="c-num"><span>#${i + 2}</span> &nbsp;·&nbsp; Strong option</div>
        <h3><a href="${ch2}" target="_blank" rel="noreferrer">${esc(m.creator_name)}</a></h3>
        <div class="c-stats">${compact(m.subscribers)} subs · ${esc(m.country || "Unknown")} · ${esc(m.engagement_rate)}</div>
        <div class="c-score"><div class="n">${pct2}<sup>/100</sup></div><div class="label">Fit &nbsp;·&nbsp; ${esc(m.confidence || "medium")}</div></div>
        <p>${esc(m.reasoning || "")}</p>
        ${ribbonHtml(m.score_components, { mini: true })}
        ${(m.recent_videos && m.recent_videos.length) ? `<div class="refs" style="grid-template-columns:1fr;padding:14px 0 0;border-top:1px solid var(--hair-2);margin-top:14px;"><div class="refs-list">${m.recent_videos.slice(0,3).map((v,k)=>`<a href="${v.url}" target="_blank" rel="noreferrer"><span>${esc(v.title||("Recent video "+(k+1)))}</span><span class="ext">youtube.com</span></a>`).join("")}</div></div>` : ""}
        <div class="hero-actions" style="margin-top:14px">
          <a class="cta ghost" href="${ch2}" target="_blank" rel="noreferrer">${EXT}Channel</a>
          <a class="cta ghost" href="#" data-sched-creator="${esc(m.creator_name)}">${CAL}Schedule</a>
          <a class="cta ghost" href="#" data-outreach-creator="${esc(m.creator_name)}" data-outreach-topics="${esc(m.content_topics||"")}" data-outreach-titles="${esc((m.recent_videos||[]).slice(0,5).map(v=>v.title).join(", "))}" data-outreach-reasoning="${esc(m.reasoning||"")}">${MAIL}Outreach</a>
          <a class="cta ghost" href="#" data-add-dossier="${esc(JSON.stringify({type:'creator', id:m.channel_id, name:m.creator_name, data:m}))}">${PLUS}Dossier</a>
        </div>
      </article>`;
    }).join("");

    out.innerHTML = hero + (runners ? `<div class="rule" style="margin-top:40px"><span class="num">03</span> Strong options</div><div class="runners">${runners}</div>` : "");
}

function renderBrandOpportunities(matches, creatorName, creatorBrief) {
    const out = $("results");
    if (!matches.length) {
        out.innerHTML = `<div class="empty"><h2>No matching campaigns.</h2><p>Try adjusting the channel summary.</p></div>`;
        return;
    }
    const [top, ...rest] = matches;
    const pct = Math.round(Number(top.fit_score || 0));

    const creatorSide = `
    <div class="panel left">
      <div class="p-eyebrow">Your channel · Creator</div>
      <div class="p-title">${esc(creatorName || "—")}</div>
      <div class="p-body">${esc(creatorBrief || "—")}</div>
    </div>`;
    // Right panel shows the brand's own voice (description) — NOT the creator-fit reasoning.
    const brandBlurb = top.description || top.campaign_brief || top.why || "";
    const brandSide = `
    <div class="panel right">
      <div class="p-eyebrow">Recommended match · Brand</div>
      <div class="p-title">${esc(top.brand_name)}</div>
      <div class="p-body">${esc(brandBlurb)}</div>
      <div class="tags">${top.industry ? `<span class="tag">${esc(top.industry)}</span>` : ""}${top.budget_range ? `<span class="tag">${esc(top.budget_range)}</span>` : ""}</div>
    </div>`;

    const hero = `
    <article class="match">
      <div class="match-header">
        <div>
          <div class="m-kicker">Recommended · ${esc(top.confidence || "medium")} confidence</div>
          <h2>${esc(top.brand_name)}</h2>
          <div class="stats"><strong>${esc(top.industry || "Brand")}</strong> &nbsp;·&nbsp; ${esc(top.budget_range || "Budget TBD")} &nbsp;·&nbsp; channel engagement ${esc(top.engagement_rate || "N/A")}</div>
        </div>
      </div>
      <div class="split">
        ${creatorSide}
        <div class="seam">
          <div class="numeral">${pct}<sup>/100</sup></div>
          <div class="label">Fit</div>
          <div class="conf">${esc(top.confidence || "medium")} confidence</div>
        </div>
        ${brandSide}
      </div>
      <p class="reasoning">${esc(top.why || "")}</p>
      <p class="reasoning" style="margin-top:10px"><strong style="color:var(--accent-deep);font-family:'JetBrains Mono',monospace;text-transform:uppercase;font-size:10.5px;letter-spacing:.14em;font-weight:500">Pitch angle</strong> ${esc(top.pitch_angle || "")}</p>
      ${top.risks ? `<div class="risks"><strong>Risks</strong>${esc(Array.isArray(top.risks) ? top.risks.join(" · ") : top.risks)}</div>` : ""}
      <div class="actions">
        <a class="primary" href="#" data-sched-brand="${esc(top.brand_name)}">${CAL}Schedule intro call</a>
        <a href="#" data-outreach-brand="${esc(top.brand_name)}" data-outreach-brief="${esc(top.campaign_brief||top.description||"")}">${MAIL}Draft outreach</a>
        <a href="#" data-add-dossier="${esc(JSON.stringify({type:'brand', id:top.brand_name, name:top.brand_name, data:top}))}">${PLUS}Add to Dossier</a>
      </div>
    </article>`;

    const runners = rest.slice(0, 2).map((m, i) => {
        const pct2 = Math.round(Number(m.fit_score || 0));
        return `
      <article class="card">
        <div class="c-num"><span>#${i + 2}</span> &nbsp;·&nbsp; Potential sponsor</div>
        <h3>${esc(m.brand_name)}</h3>
        <div class="c-stats">${esc(m.industry || "Brand")} · ${esc(m.budget_range || "Budget TBD")}</div>
        <div class="c-score"><div class="n">${pct2}<sup>/100</sup></div><div class="label">Fit &nbsp;·&nbsp; ${esc(m.confidence || "medium")}</div></div>
        <p>${esc(m.description || m.campaign_brief || "")}</p>
        <p style="margin-top:8px;font-size:12.5px;color:var(--ink-2);font-style:italic;font-family:Newsreader,serif">${esc(m.why || "")}</p>
        <p style="margin-top:8px;font-size:12.5px;color:var(--muted)"><strong style="color:var(--accent-deep);font-family:'JetBrains Mono',monospace;text-transform:uppercase;font-size:10.5px;letter-spacing:.14em;font-weight:500">Pitch</strong> ${esc(m.pitch_angle || "")}</p>
        <div class="hero-actions" style="margin-top:14px">
          <a class="cta ghost" href="#" data-sched-brand="${esc(m.brand_name)}">${CAL}Schedule</a>
          <a class="cta ghost" href="#" data-outreach-brand="${esc(m.brand_name)}" data-outreach-brief="${esc(m.campaign_brief || m.description || "")}">${MAIL}Outreach</a>
          <a class="cta ghost" href="#" data-add-dossier="${esc(JSON.stringify({type:'brand', id:m.brand_name, name:m.brand_name, data:m}))}">${PLUS}Dossier</a>
        </div>
      </article>`;
    }).join("");

    out.innerHTML = hero + (runners ? `<div class="rule" style="margin-top:40px"><span class="num">03</span> Potential sponsors</div><div class="runners">${runners}</div>` : "");
}

// ── Live agent pipeline ──────────────────────────────────

// ── Minimal markdown renderer for agent prose (### / ** / lists / hr) ──
function renderMarkdown(src) {
    let s = String(src || "");
    // Pre-escape HTML
    s = s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    // Links: [label](url) → <a>
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
    // Bare URLs
    s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noreferrer">$2</a>');
    // Split by blank lines into blocks
    const blocks = s.split(/\n\s*\n/);
    const out = [];
    for (let block of blocks) {
        block = block.trim();
        if (!block) continue;
        // Horizontal rule
        if (/^-{3,}$/.test(block)) { out.push('<hr class="md-hr">'); continue; }
        // Heading ### / ####
        let h = block.match(/^(#{2,4})\s+(.+)$/);
        if (h) { const lvl = Math.min(h[1].length + 1, 6); out.push(`<h${lvl} class="md-h">${inlineMd(h[2])}</h${lvl}>`); continue; }
        // Ordered list (numbered entries across multiple lines; supports multi-line items)
        if (/^\d+\.\s/.test(block)) {
            // Split into items on "\nN." where N is the next number
            const items = block.split(/\n(?=\d+\.\s)/).map((it) => it.replace(/^\d+\.\s+/, "").trim());
            out.push('<ol class="md-ol">' + items.map((it) => `<li>${inlineMd(it).replace(/\n/g, "<br>")}</li>`).join("") + '</ol>');
            continue;
        }
        // Unordered list (- or *)
        if (/^[-*]\s/.test(block)) {
            const items = block.split(/\n(?=[-*]\s)/).map((it) => it.replace(/^[-*]\s+/, "").trim());
            out.push('<ul class="md-ul">' + items.map((it) => `<li>${inlineMd(it).replace(/\n/g, "<br>")}</li>`).join("") + '</ul>');
            continue;
        }
        // Fallback paragraph
        out.push(`<p class="md-p">${inlineMd(block).replace(/\n/g, "<br>")}</p>`);
    }
    return out.join("");
}
function inlineMd(s) {
    // Bold **x**
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // Italic *x* (simple — not inside words)
    s = s.replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    // Inline code `x`
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    return s;
}

function renderPipelineCompact(activity) {
    if (!Array.isArray(activity) || !activity.length) return "";
    const steps = activity.map((a) => `<div class="step"><div class="dot filled"></div><div class="step-body"><strong>${esc(a.tool)}</strong><span>${esc(a.summary || "")}</span></div></div>`).join("");
    // Collapsed by default — judges can expand to inspect the tool calls.
    return `<article class="pipeline collapsed" style="margin-bottom:22px">
    <button type="button" class="pipeline-head pipeline-toggle" aria-expanded="false">
      <div class="lbl">Live agent trace</div>
      <div class="count">${activity.length} tool call${activity.length === 1 ? "" : "s"} <span class="chevron">▾</span></div>
    </button>
    <div class="pipeline-body"><div class="steps">${steps}</div></div>
  </article>`;
}

function renderAgent(data) {
    const activity = Array.isArray(data.activity) ? data.activity : [];
    const matches = Array.isArray(data.top_matches) ? data.top_matches : [];
    const brandMatches = Array.isArray(data.brand_matches) ? data.brand_matches : [];
    const body = data.agent_text || data.detail || data.error || "";

    // Brand mode: creator-shaped records from score_creator_fit → creator shortlist dossier.
    const canUseCreatorDossier = matches.length && mode === "brand" && matches[0].creator_name;
    // Creator mode: brand_matches were stitched server-side by matching each
    // score_creator_fit call's brand_brief to the DB brand table.
    const canUseBrandDossier = brandMatches.length && mode === "creator" && brandMatches[0].brand_name;

    if (canUseCreatorDossier) {
        const pipelineHtml = renderPipelineCompact(activity);
        renderCreatorShortlist(matches, $("nameInput").value.trim(), $("briefInput").value.trim());
        $("results").innerHTML = pipelineHtml + $("results").innerHTML;
        if (data.media_kit) renderKit(data.media_kit, data.saved_message); else $("kit").innerHTML = "";
        showRefinePanel();
        return;
    }
    if (canUseBrandDossier) {
        const pipelineHtml = renderPipelineCompact(activity);
        renderBrandOpportunities(brandMatches, $("nameInput").value.trim(), $("briefInput").value.trim());
        $("results").innerHTML = pipelineHtml + $("results").innerHTML;
        if (data.media_kit) renderKit(data.media_kit, data.saved_message); else $("kit").innerHTML = "";
        showRefinePanel();
        return;
    }

    // Fallback: prose-only response (agent didn't complete scoring, or tool errors).
    const steps = activity.length
        ? activity.map((a) => `<div class="step"><div class="dot filled"></div><div class="step-body"><strong>${esc(a.tool)}</strong><span>${esc(a.summary || "")}</span></div></div>`).join("")
        : `<div class="step"><div class="dot"></div><div class="step-body"><span>No tool calls captured.</span></div></div>`;
    $("results").innerHTML = `
    <article class="pipeline">
      <button type="button" class="pipeline-head pipeline-toggle" aria-expanded="true">
        <div class="lbl">Live agent run</div>
        <div class="count">${activity.length} tool call${activity.length === 1 ? "" : "s"} <span class="chevron">▾</span></div>
      </button>
      <div class="pipeline-body"><div class="steps">${steps}</div></div>
      ${body ? `<div class="agent-text">${renderMarkdown(body)}</div>` : ""}
    </article>`;
    $("kit").innerHTML = "";
}

// ── Loading skeleton ─────────────────────────────────────
let _skelTimer = null;
function renderLoading(kind) {
    const phases = kind === "agent"
        ? [
            "Searching YouTube for candidate creators…",
            "Pulling channel details and recent videos…",
            "Scoring every candidate on eight signals…",
            "Ranking, tie-breaking, and assembling the dossier…",
            "Drafting the media kit and saving the match…",
        ]
        : [
            "Scoring candidates deterministically…",
            "Ranking by fit, confidence, and risk…",
            "Assembling the dossier…",
        ];
    let i = 0;
    $("results").innerHTML = `
    <div class="skeleton">
      <div class="sk-kicker">In progress · ${kind === "agent" ? "Multi-agent crew" : "Deterministic scoring"}</div>
      <div class="sk-phase"><span class="phase-text" id="phaseText">${esc(phases[0])}</span></div>
      <div class="sk-grid">
        <div class="sk-panel l"><div class="sk-bar w60"></div><div class="sk-bar w90"></div><div class="sk-bar w80"></div><div class="sk-bar w70"></div></div>
        <div class="sk-seam"><div class="sk-ring"></div></div>
        <div class="sk-panel"><div class="sk-bar w60"></div><div class="sk-bar w80"></div><div class="sk-bar w90"></div><div class="sk-bar w45"></div></div>
      </div>
      <div class="sk-activity">
        <div class="sk-step"><div class="sk-dot on"></div><div class="sk-bar w60" style="margin:0"></div></div>
        <div class="sk-step"><div class="sk-dot on"></div><div class="sk-bar w70" style="margin:0"></div></div>
        <div class="sk-step"><div class="sk-dot"></div><div class="sk-bar w45" style="margin:0"></div></div>
        <div class="sk-step"><div class="sk-dot"></div><div class="sk-bar w60" style="margin:0"></div></div>
      </div>
    </div>`;
    $("kit").innerHTML = "";
    clearInterval(_skelTimer);
    _skelTimer = setInterval(() => {
        i = (i + 1) % phases.length;
        const el = document.getElementById("phaseText");
        if (!el) { clearInterval(_skelTimer); return; }
        el.classList.add("out");
        setTimeout(() => {
            el.textContent = phases[i];
            el.classList.remove("out");
        }, 260);
    }, 2800);
}
function clearLoading() { clearInterval(_skelTimer); _skelTimer = null; }

// ── Media kit ────────────────────────────────────────────
function renderKit(kit, savedMessage) {
    if (!kit) { $("kit").innerHTML = ""; return; }
    const row = (dt, dd) => `<div class="dl-row"><dt>${dt}</dt><dd>${dd}</dd></div>`;
    $("kit").innerHTML = `
    <div class="rule"><span class="num">04</span> Media kit</div>
    <div class="kit">
      <h3>${esc(kit.creator_name || "")}</h3>
      <div class="k-sub">Prepared for the recommended brand match.</div>
      <dl>
        ${row("Channel", `<a href="${kit.channel_url}" target="_blank" rel="noreferrer">${esc(kit.channel_url || "")}</a>`)}
        ${row("Subscribers", Number(kit.subscribers || 0).toLocaleString())}
        ${row("Total views", Number(kit.total_views || 0).toLocaleString())}
        ${row("Avg views / video", Number(kit.avg_views_per_video || 0).toLocaleString())}
        ${row("Engagement", esc(kit.engagement_rate || "—"))}
        ${row("Country", esc(kit.country || "Unknown"))}
        ${row("Top topics", esc((kit.top_content_topics || []).join(", ")))}
        ${row("Formats", esc((kit.collaboration_formats || []).join(" · ")))}
      </dl>
      ${savedMessage ? `<p style="margin-top:20px;font-size:12.5px;color:var(--muted);font-family:'JetBrains Mono',monospace">${esc(savedMessage)}</p>` : ""}
    </div>`;
}

// ── Mode switching ───────────────────────────────────────
function setMode(next) {
    mode = next;
    document.body.classList.toggle("creator-mode", mode === "creator");
    $("brandTab").classList.toggle("active", mode === "brand");
    $("creatorTab").classList.toggle("active", mode === "creator");
    $("nameLabel").textContent = mode === "brand" ? "Brand name" : "Creator name";
    $("briefLabel").textContent = mode === "brand" ? "Campaign brief" : "Channel summary";
    $("briefKicker").textContent = mode === "brand" ? "The brief" : "Your channel";
    $("briefHeadline").innerHTML = mode === "brand"
        ? `Describe the campaign. <em>We'll find the creator.</em>`
        : `Describe your channel. <em>We'll find the sponsor.</em>`;
    $("briefSub").textContent = mode === "brand"
        ? "A deterministic scoring engine and a live multi-agent crew assemble your shortlist, media kit, and introduction call."
        : "A deterministic scoring engine ranks live brand campaigns in the database and drafts pitch angles for your channel.";
    $("matchBtnLabel").textContent = mode === "brand" ? "Find my match" : "Find my sponsor";

    const first = scenarios[mode][0];
    $("nameInput").value = first.name;
    $("briefInput").value = first.brief;
    renderScenarios();

    const [l, r] = mode === "brand" ? ["B", "C"] : ["C", "B"];
    $("results").innerHTML = `
    <div class="empty">
      <div class="empty-art">
        <div class="portrait b">${l}</div>
        <div class="tie"></div>
        <div class="portrait">${r}</div>
      </div>
      <h2>Two sides, <em>one good match.</em></h2>
      <p>${mode === "brand" ? "Complete the brief, then press <strong>Find my match</strong>. A multi-agent crew searches YouTube, scores every candidate on eight deterministic signals, and stitches the full dossier together." : "Complete your channel summary, then press <strong>Find my sponsor</strong>. The agent ranks active brand campaigns in the database and drafts pitch angles tuned to your audience."}</p>
    </div>`;
    $("kit").innerHTML = "";
  hideRefinePanel();
}

function renderScenarios() {
    $("scenarios").innerHTML = scenarios[mode].map((s, i) =>
        `<button type="button" class="scenario" data-i="${i}">${esc(s.label)}</button>`
    ).join("");
    document.querySelectorAll(".scenario").forEach((b) => {
        b.addEventListener("click", () => {
            const s = scenarios[mode][Number(b.dataset.i)];
            $("nameInput").value = s.name;
            $("briefInput").value = s.brief;
            runPreview();
        });
    });
}

function creatorFromForm() {
    const text = $("briefInput").value.trim();
    return {
        creator_name: $("nameInput").value.trim() || "Creator Demo",
        channel_id: "UCdemoCreatorFromForm0001",
        subscribers: 149000, total_views: 23360000, avg_views: 18800,
        content_topics: text,
        country: text.toLowerCase().includes("southeast asia") ? "SG" : "US",
        channel_description: text,
        recent_video_titles: "Zero Waste Bathroom Reset, Sustainable Home Swaps That Last, Thrifted Kitchen Makeover, Vegan Self Care Routine",
        recent_video_dates: "2026-04-17,2026-04-03,2026-03-20,2026-03-06",
        video_count: 178, shorts_ratio: 0,
        total_likes_recent: 5480, total_comments_recent: 690, total_views_recent: 92000,
    };
}

function setStatus(text, active) {
    const el = $("status");
    el.textContent = text || "";
    el.classList.toggle("active", !!active);
}

async function runLive() {
  lastRun = {kind:"live", mode};
    $("matchBtn").disabled = true;
    setStatus("Running multi-agent crew · Vertex AI · MCP tools", true);
    renderLoading("agent");
    try {
        const message = mode === "brand"
            ? `${$("briefInput").value.trim()}\n\nBrand name: ${$("nameInput").value.trim() || "Demo Brand"}`
            : `${$("briefInput").value.trim()}\n\nCreator name: ${$("nameInput").value.trim() || "Demo Creator"}`;
        const r = await fetch("/api/agent-run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) });
        if (!r.ok) throw new Error(await r.text());
        const data = await r.json();
        if (data.error) throw new Error(`${data.error}${data.detail ? ": " + data.detail : ""}`);
        renderAgent(data);
        setStatus("Ready");
    } catch (err) {
        setStatus("Agent error");
        $("results").innerHTML = `<div class="empty"><h2>Agent run failed.</h2><p>${esc(String(err.message || err))}</p></div>`;
        $("kit").innerHTML = "";
    } finally {
        clearLoading();
        $("matchBtn").disabled = false;
    }
}

async function runPreview() {
  lastRun = {kind:"preview", mode};
    $("previewBtn").disabled = true;
    setStatus("Scoring deterministically · SQLite persistence", true);
    renderLoading("preview");
    try {
        const endpoint = mode === "brand" ? "/api/score" : "/api/creator-match";
        const body = mode === "brand"
            ? { brand_name: $("nameInput").value.trim() || "Demo Brand", brand_brief: $("briefInput").value.trim(), save_top_match: true }
            : { creator: creatorFromForm() };
        const r = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (!r.ok) throw new Error(await r.text());
        const data = await r.json();
        if (mode === "brand") {
            renderCreatorShortlist(data.top_matches || [], data.brand_name, $("briefInput").value.trim());
        } else {
            renderBrandOpportunities(data.brand_matches || [], data.creator_name, $("briefInput").value.trim());
        }
        renderKit(data.media_kit, data.saved_message);
        showRefinePanel();
        setStatus("Ready");
    } catch (err) {
        setStatus("Error");
        $("results").innerHTML = `<div class="empty"><h2>Preview failed.</h2><p>${esc(String(err.message || err))}</p></div>`;
        $("kit").innerHTML = "";
    } finally {
        clearLoading();
        $("previewBtn").disabled = false;
    }
}

$("brandTab").addEventListener("click", () => setMode("brand"));
$("creatorTab").addEventListener("click", () => setMode("creator"));
$("matchBtn").addEventListener("click", runLive);
$("previewBtn").addEventListener("click", runPreview);
// ── Schedule modal ─────────────────────────────────────────
function nextTuesdayISO() {
    const d = new Date();
    const target = 2; // Tuesday
    const diff = (target - d.getDay() + 7) % 7 || 7;
    d.setDate(d.getDate() + diff);
    return d.toISOString().slice(0, 10);
}
function updateSchedPreview() {
    const who = document.getElementById("schedModal").dataset.who || "the match";
    const d = $("schedDate").value;
    const t = $("schedTime").value;
    const dur = $("schedDuration").value;
    const tz = $("schedTimezone").value;
    $("schedPreview").textContent = `Schedule an intro call with ${who} on ${d} at ${t} for ${dur} minutes (${tz}).`;
}
function openSchedule(who) {
    const modal = $("schedModal");
    modal.dataset.who = who || "the match";
    if (!$("schedDate").value) $("schedDate").value = nextTuesdayISO();
    updateSchedPreview();
    modal.classList.remove("hidden");
    setTimeout(() => $("schedConfirm").focus(), 60);
}
function closeSchedule() { $("schedModal").classList.add("hidden"); }

document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-sched-creator],[data-sched-brand]");
    if (!a) return;
    e.preventDefault();
    const who = a.getAttribute("data-sched-creator") || a.getAttribute("data-sched-brand") || "the match";
    openSchedule(who);
});
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("schedModal").classList.contains("hidden")) closeSchedule();
});
document.getElementById("schedCancel").addEventListener("click", closeSchedule);
document.getElementById("schedModal").addEventListener("click", (e) => {
    if (e.target.id === "schedModal") closeSchedule();
});
["schedDate", "schedTime", "schedDuration", "schedTimezone"].forEach((id) => {
    document.getElementById(id).addEventListener("input", updateSchedPreview);
});
document.getElementById("schedConfirm").addEventListener("click", async () => {
    const who = $("schedModal").dataset.who || "the match";
    const d = $("schedDate").value, t = $("schedTime").value;
    const dur = $("schedDuration").value, tz = $("schedTimezone").value;
    const msg = `Schedule an intro call with ${who} on ${d} at ${t} for ${dur} minutes (${tz}). Attendees: demo@example.com.`;
    closeSchedule();
    $("matchBtn").disabled = true;
    setStatus("Running scheduling agent · Google Calendar MCP", true);
    renderLoading("agent");
    try {
        const r = await fetch("/api/agent-run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: msg }) });
        if (!r.ok) throw new Error(await r.text());
        const data = await r.json();
        if (data.error) throw new Error(`${data.error}${data.detail ? ": " + data.detail : ""}`);
        renderAgent(data);
        setStatus("Ready");
    } catch (err) {
        setStatus("Scheduling error");
        $("results").innerHTML = `<div class="empty"><h2>Scheduling failed.</h2><p>${esc(String(err.message || err))}</p></div>`;
    } finally {
        clearLoading();
        $("matchBtn").disabled = false;
    }
});
setMode("brand");

// ── Refinement loop ────────────────────────────────────────
function ensureRefinePanel() {
  let panel = document.getElementById("refinePanel");
  if (panel) return panel;
  panel = document.createElement("section");
  panel.className = "refine";
  panel.id = "refinePanel";
  panel.innerHTML = `
    <div class="r-eyebrow">Refine · iterate the brief</div>
    <h3>Not quite right? <em>Tell us what to change.</em></h3>
    <p class="r-sub">Add a constraint, narrow the audience, or exclude a niche. The agent will append your refinement to the brief and re-run.</p>
    <div class="r-row">
      <input type="text" id="refineInput" placeholder="e.g. EU-based only, exclude Shorts-heavy creators, prefer micro-creators under 100K">
      <button type="button" id="refineGo">Refine &amp; re-run</button>
    </div>
    <div class="r-suggestions" id="refineSuggestions"></div>
  `;
  // Append after results/kit so the panel is always visible after a render.
  const kit = document.getElementById("kit");
  const results = document.getElementById("results");
  const anchor = (kit && kit.parentNode) ? kit : results;
  if (anchor && anchor.parentNode) {
    anchor.parentNode.insertBefore(panel, anchor.nextSibling);
  } else {
    document.querySelector("main.col").appendChild(panel);
  }
  document.getElementById("refineGo").addEventListener("click", runRefine);
  document.getElementById("refineInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") runRefine();
  });
  return panel;
}

function showRefinePanel() {
  const panel = ensureRefinePanel();
  // Different suggestion chips depending on mode
  const suggestions = mode === "brand"
    ? ["EU-based creators only", "Exclude Shorts-heavy channels", "Prefer micro-creators under 100K subs", "Must have posted in last 30 days"]
    : ["Higher budget brands ($10k+)", "Tech & gadget focus only", "Avoid food and beverage brands", "Prefer brands with long-form video formats"];
  document.getElementById("refineSuggestions").innerHTML = suggestions
    .map((s) => `<button type="button" class="r-chip">${esc(s)}</button>`).join("");
  document.querySelectorAll("#refineSuggestions .r-chip").forEach((b) => {
    b.addEventListener("click", () => {
      const inp = document.getElementById("refineInput");
      inp.value = (inp.value ? inp.value + ", " : "") + b.textContent;
      inp.focus();
    });
  });
  panel.classList.add("active");
}

function hideRefinePanel() {
  const p = document.getElementById("refinePanel");
  if (p) p.classList.remove("active");
}

async function runRefine() {
  const refinement = document.getElementById("refineInput").value.trim();
  if (!refinement) return;
  if (!lastRun) {
    alert("Run a search first, then refine the result.");
    return;
  }
  // Append refinement to the brief, preserving the original
  const briefEl = $("briefInput");
  const original = briefEl.value.trim();
  briefEl.value = `${original}\n\nRefinement: ${refinement}`;
  document.getElementById("refineInput").value = "";
  // Re-fire the same path the user used last
  if (lastRun.kind === "live") await runLive();
  else await runPreview();
}

// ── Outreach draft ─────────────────────────────────────────
function openOutreach(payload) {
  const modal = document.getElementById("outreachModal");
  document.getElementById("outreachWho").textContent = payload.label || "your top match";
  document.getElementById("outreachText").style.display = "none";
  document.getElementById("outreachText").value = "";
  const status = document.getElementById("outreachStatus");
  status.textContent = "Drafting...";
  status.classList.add("active");
  status.style.display = "flex";
  document.getElementById("outreachCopy").disabled = true;
  modal.classList.remove("hidden");

  fetch("/api/outreach-draft", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload.body)
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) throw new Error(`${data.error}${data.detail?": "+data.detail:""}`);
      const ta = document.getElementById("outreachText");
      ta.value = data.draft || "(empty draft returned)";
      ta.style.display = "block";
      status.style.display = "none";
      document.getElementById("outreachCopy").disabled = false;
    })
    .catch((err) => {
      status.classList.remove("active");
      status.textContent = "Failed: " + (err.message || err);
    });
}
function closeOutreach() {
  document.getElementById("outreachModal").classList.add("hidden");
}

// Wire the outreach + refine triggers via event delegation
document.addEventListener("click", (e) => {
  const oCreator = e.target.closest("[data-outreach-creator]");
  if (oCreator) {
    e.preventDefault();
    openOutreach({
      label: oCreator.getAttribute("data-outreach-creator"),
      body: {
        brand_name: $("nameInput").value.trim() || "Demo Brand",
        brand_brief: $("briefInput").value.trim(),
        creator_name: oCreator.getAttribute("data-outreach-creator"),
        creator_topics: oCreator.getAttribute("data-outreach-topics") || "",
        recent_video_titles: oCreator.getAttribute("data-outreach-titles") || "",
        match_reasoning: oCreator.getAttribute("data-outreach-reasoning") || "",
        sender_first_name: $("nameInput").value.split(/\s+/)[0] || "Mabel",
        mode: "brand_to_creator",
      }
    });
    return;
  }
  const oBrand = e.target.closest("[data-outreach-brand]");
  if (oBrand) {
    e.preventDefault();
    openOutreach({
      label: oBrand.getAttribute("data-outreach-brand"),
      body: {
        brand_name: oBrand.getAttribute("data-outreach-brand"),
        brand_brief: oBrand.getAttribute("data-outreach-brief") || "",
        creator_name: $("nameInput").value.trim() || "Demo Creator",
        creator_topics: $("briefInput").value.trim(),
        recent_video_titles: "",
        match_reasoning: "Creator-mode reverse pitch",
        sender_first_name: ($("nameInput").value || "Mabel").split(/\s+/)[0],
        mode: "creator_to_brand",
      }
    });
    return;
  }
});

document.getElementById("outreachClose").addEventListener("click", closeOutreach);
document.getElementById("outreachCopy").addEventListener("click", async () => {
  const txt = document.getElementById("outreachText").value;
  try {
    await navigator.clipboard.writeText(txt);
    const btn = document.getElementById("outreachCopy");
    const orig = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = orig; }, 1200);
  } catch (err) {
    alert("Could not copy automatically. Select the text manually.");
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !document.getElementById("outreachModal").classList.contains("hidden")) closeOutreach();
});
document.getElementById("outreachModal").addEventListener("click", (e) => {
  if (e.target.id === "outreachModal") closeOutreach();
});

// Pipeline collapse/expand
document.addEventListener("click", (e) => {
  const t = e.target.closest(".pipeline-toggle");
  if (!t) return;
  const article = t.closest(".pipeline");
  if (!article) return;
  article.classList.toggle("collapsed");
  t.setAttribute("aria-expanded", String(!article.classList.contains("collapsed")));
});

// ── Dossier & Session Management ──────────────────────────

const Dossier = {
    items: [],
    sessionId: null,

    init() {
        this.sessionId = localStorage.getItem("sb_session_id");
        if (!this.sessionId) {
            this.sessionId = Math.random().toString(36).substring(2, 15);
            localStorage.setItem("sb_session_id", this.sessionId);
        }
        
        this.bindEvents();
        this.fetch();
    },

    bindEvents() {
        $("dossierBtn").addEventListener("click", () => this.toggle(true));
        $("closeDossier").addEventListener("click", () => this.toggle(false));
        $("drawerBackdrop").addEventListener("click", () => {
            this.toggle(false);
            this.toggleResult(false);
        });
        $("generatePromptBtn").addEventListener("click", () => this.generatePrompt());
        $("closeResultPanel").addEventListener("click", () => this.toggleResult(false));
        $("copyResultBtn").addEventListener("click", () => this.copyResult());

        // Event delegation for adding/removing items
        document.addEventListener("click", (e) => {
            const addBtn = e.target.closest("[data-add-dossier]");
            if (addBtn) {
                e.preventDefault();
                const item = JSON.parse(addBtn.dataset.addDossier);
                this.add(item);
            }

            const removeBtn = e.target.closest(".remove-item");
            if (removeBtn) {
                e.preventDefault();
                const { type, id } = removeBtn.dataset;
                this.remove(type, id);
            }
        });
    },

    async fetch() {
        try {
            const r = await fetch(`/api/dossier?session_id=${this.sessionId}`);
            const data = await r.json();
            this.items = data.items || [];
            this.render();
        } catch (err) {
            console.error("Failed to fetch dossier", err);
        }
    },

    async add(item) {
        // Prevent duplicates
        if (this.items.some(i => i.type === item.type && i.id === item.id)) {
            this.toggle(true);
            return;
        }

        try {
            await fetch("/api/dossier", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    ...item
                })
            });
            this.items.push(item);
            this.render();
            this.toggle(true);
        } catch (err) {
            console.error("Failed to add to dossier", err);
        }
    },

    async remove(type, id) {
        try {
            await fetch("/api/dossier", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    type,
                    id
                })
            });
            this.items = this.items.filter(i => !(i.type === type && i.id === id));
            this.render();
        } catch (err) {
            console.error("Failed to remove from dossier", err);
        }
    },

    toggle(show) {
        $("dossierDrawer").classList.toggle("hidden", !show);
        $("drawerBackdrop").classList.toggle("hidden", !show);
        if (!show) this.toggleResult(false);
    },

    toggleResult(show) {
        $("dossierResultPanel").classList.toggle("hidden", !show);
    },

    render() {
        const list = $("dossierItems");
        $("dossierCount").textContent = this.items.length;
        
        if (this.items.length === 0) {
            list.innerHTML = `<div class="empty-dossier">Your dossier is empty. Add creators or brands to get started.</div>`;
            return;
        }

        list.innerHTML = this.items.map(item => `
            <div class="dossier-item">
                <div class="item-info">
                    <span class="item-type">${esc(item.type)}</span>
                    <span class="item-name">${esc(item.name)}</span>
                </div>
                <button class="remove-item" data-type="${esc(item.type)}" data-id="${esc(item.id)}" title="Remove">&times;</button>
            </div>
        `).join("");
    },

    async generatePrompt() {
        const input = $("customPromptInput");
        const instruction = input.value.trim();
        const btn = $("generatePromptBtn");
        const resultDiv = $("promptResult");

        if (!instruction) return;
        if (this.items.length === 0) {
            alert("Add some items to your dossier first.");
            return;
        }

        btn.disabled = true;
        btn.textContent = "Generating...";
        resultDiv.classList.add("hidden");

        try {
            const r = await fetch("/api/custom-prompt", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    instruction
                })
            });
            const data = await r.json();
            if (data.error) throw new Error(data.error);

            const html = renderMarkdown(data.result);
            $("dossierResultText").innerHTML = html;
            this.toggleResult(true);
        } catch (err) {
            alert("Generation failed: " + err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = "Generate Prompt";
        }
    },

    async copyResult() {
        const txt = $("dossierResultText").innerText;
        try {
            await navigator.clipboard.writeText(txt);
            const btn = $("copyResultBtn");
            const orig = btn.textContent;
            btn.textContent = "Copied!";
            setTimeout(() => { btn.textContent = orig; }, 1200);
        } catch (err) {
            alert("Could not copy automatically.");
        }
    }
};

Dossier.init();
