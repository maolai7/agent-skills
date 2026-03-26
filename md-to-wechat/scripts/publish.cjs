/**
 * publish.cjs - 将本地 Markdown 文章渲染为微信公众号格式并推送到草稿箱
 *
 * 作用：
 *   1. 检查本机公网 IP（微信 API IP 白名单）
 *   2. 调用渲染服务将 MD 转为微信 HTML（内存中处理，不生成本地文件）
 *   3. 获取微信 access_token
 *   4. 上传封面图为永久素材（带本地缓存，相同图片不重复上传）
 *   5. 将正文外部图片上传到微信 CDN（微信只能显示自己 CDN 的图片）
 *   6. 推送到微信公众号草稿箱
 *
 * 用法：
 *   首次运行（检查 IP）：
 *     node publish.cjs --file <md文件路径>
 *   确认 IP 已加入白名单后正式推送：
 *     node publish.cjs --file <md文件路径> --confirmed [--title <标题>] [--author <作者>] [--cover <封面图>]
 *
 * 封面图优先级：--cover 参数 > MD 文件中第一张图 > .env 的 WECHAT_DEFAULT_COVER
 *
 * 依赖：Node.js 18+（内置 fetch / FormData / Blob），零 npm 依赖
 */
'use strict';

const fs   = require('fs');
const path = require('path');

// ── 读取 .env ──────────────────────────────────────────────────────────────
const envPath = path.join(__dirname, '..', '.env');
if (fs.existsSync(envPath)) {
  fs.readFileSync(envPath, 'utf-8').split('\n').forEach(line => {
    const m = line.match(/^\s*([^#=\s][^=]*?)\s*=\s*(.*?)\s*$/);
    if (m) process.env[m[1]] = m[2];
  });
}

// ── 常量 ───────────────────────────────────────────────────────────────────
const FALLBACK_COVER = 'https://zaowu-pic.maolai.cc/uploads/1774501229309-Image_55.jpg';
const WECHAT_API     = 'https://api.weixin.qq.com/cgi-bin';
const CACHE_PATH     = path.join(__dirname, '..', '.cache.json');

// ── 解析命令行参数 ─────────────────────────────────────────────────────────
function parseArgs(argv) {
  const args = { confirmed: false };
  for (let i = 0; i < argv.length; i++) {
    if      (argv[i] === '--file')      args.file      = argv[++i];
    else if (argv[i] === '--title')     args.title     = argv[++i];
    else if (argv[i] === '--author')    args.author    = argv[++i];
    else if (argv[i] === '--cover')     args.cover     = argv[++i];
    else if (argv[i] === '--confirmed') args.confirmed = true;
  }
  return args;
}

// ── 输出辅助 ───────────────────────────────────────────────────────────────
function exitOk(data) {
  console.log(JSON.stringify(data, null, 2));
  process.exit(0);
}

function exitErr(error, message) {
  console.error(JSON.stringify({ success: false, error, message }, null, 2));
  process.exit(1);
}

// ── 缓存操作 ───────────────────────────────────────────────────────────────
function loadCache() {
  try {
    return JSON.parse(fs.readFileSync(CACHE_PATH, 'utf-8'));
  } catch {
    return { covers: {}, bodyImages: {} };
  }
}

function saveCache(cache) {
  fs.writeFileSync(CACHE_PATH, JSON.stringify(cache, null, 2), 'utf-8');
}

// ── MD 文件解析 ────────────────────────────────────────────────────────────

/** 从 MD 内容提取第一个一级标题 */
function extractTitle(md) {
  const m = md.match(/^#\s+(.+)$/m);
  return m ? m[1].trim() : null;
}

/** 从 MD 内容提取第一张图片的 URL（排除代码块内的内容） */
function extractFirstImage(md) {
  const stripped = md
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`[^`\n]+`/g, '');
  const m = stripped.match(/!\[.*?\]\(((?:https?:\/\/|\.{0,2}\/)[^)\s]+)\)/);
  return m ? m[1] : null;
}

// ── 图片处理 ───────────────────────────────────────────────────────────────

/** 根据文件名猜测 MIME 类型 */
function guessMime(filename) {
  const ext = path.extname(filename).toLowerCase();
  const map = { '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp' };
  return map[ext] || 'image/jpeg';
}

/**
 * 将图片（URL 或本地路径）上传为微信永久素材，返回 media_id。
 * 优先读取缓存，避免重复上传。
 */
async function uploadCoverImage(imageSource, mdDir, token) {
  const cache = loadCache();

  if (cache.covers[imageSource]) {
    console.error(`[封面] 缓存命中，跳过上传：${imageSource}`);
    return cache.covers[imageSource];
  }

  console.error(`[封面] 正在上传封面图：${imageSource}`);

  let buffer, filename;
  const isUrl = /^https?:\/\//i.test(imageSource);

  if (isUrl) {
    const res = await fetch(imageSource);
    if (!res.ok) exitErr('cover_download_failed', `封面图下载失败（HTTP ${res.status}）：${imageSource}`);
    buffer   = Buffer.from(await res.arrayBuffer());
    filename = path.basename(new URL(imageSource).pathname) || 'cover.jpg';
  } else {
    const localPath = path.isAbsolute(imageSource) ? imageSource : path.join(mdDir, imageSource);
    if (!fs.existsSync(localPath)) exitErr('cover_not_found', `封面图文件不存在：${localPath}`);
    buffer   = fs.readFileSync(localPath);
    filename = path.basename(localPath);
  }

  const mime    = guessMime(filename);
  const form    = new FormData();
  form.append('media', new Blob([buffer], { type: mime }), filename);

  const upRes  = await fetch(`${WECHAT_API}/material/add_material?access_token=${token}&type=image`, { method: 'POST', body: form });
  const upData = await upRes.json();

  if (upData.errcode && upData.errcode !== 0) {
    const msg = upData.errmsg || JSON.stringify(upData);
    if (upData.errcode === 40164) {
      const ip = (msg.match(/invalid ip\s+([\d.]+)/i) || [])[1] || '（见错误信息）';
      exitErr('40164', `IP 不在白名单。微信看到的实际 IP：${ip}\n请加入公众号后台 → 基础信息 → API IP 白名单后重试。\n原始错误：${msg}`);
    }
    exitErr(`wechat_${upData.errcode}`, `封面图上传失败：${msg}`);
  }

  const mediaId = upData.media_id;
  if (!mediaId) exitErr('upload_no_media_id', `微信返回数据异常：${JSON.stringify(upData)}`);

  cache.covers[imageSource] = mediaId;
  saveCache(cache);
  console.error('[封面] ✅ 上传成功，media_id 已缓存');
  return mediaId;
}

/**
 * 将正文外部图片上传到微信 CDN（uploadimg 接口）。
 * 微信公众号正文只能显示微信 CDN 上的图片，外部链接会被屏蔽。
 */
async function uploadBodyImage(imageUrl, token) {
  const cache = loadCache();
  if (!cache.bodyImages) cache.bodyImages = {};

  if (cache.bodyImages[imageUrl]) {
    console.error(`  [图片] 缓存命中：${imageUrl.substring(0, 60)}...`);
    return cache.bodyImages[imageUrl];
  }

  console.error(`  [图片] 正在上传：${imageUrl.substring(0, 80)}...`);
  try {
    const res = await fetch(imageUrl);
    if (!res.ok) {
      console.error(`  [图片] ⚠️ 下载失败（HTTP ${res.status}），跳过`);
      return null;
    }
    const buffer      = Buffer.from(await res.arrayBuffer());
    const contentType = res.headers.get('content-type') || 'image/jpeg';
    const ext         = contentType.includes('png') ? '.png' : contentType.includes('gif') ? '.gif' : '.jpg';
    const form        = new FormData();
    form.append('media', new Blob([buffer], { type: contentType }), `body_img${ext}`);

    const upRes  = await fetch(`${WECHAT_API}/media/uploadimg?access_token=${token}`, { method: 'POST', body: form });
    const upData = await upRes.json();

    if (!upData.url) {
      console.error(`  [图片] ⚠️ 上传失败：${JSON.stringify(upData)}，跳过`);
      return null;
    }

    cache.bodyImages[imageUrl] = upData.url;
    saveCache(cache);
    console.error(`  [图片] ✅ 已上传 → ${upData.url.substring(0, 60)}...`);
    return upData.url;
  } catch (e) {
    console.error(`  [图片] ⚠️ 上传异常（${e.message}），跳过`);
    return null;
  }
}

/** 找出所有外部图片并替换为微信 CDN URL */
async function uploadAndReplaceBodyImages(html, token) {
  const weixinDomains = ['mmbiz.qpic.cn', 'mmbiz.qlogo.cn', 'res.wx.qq.com'];
  const srcRegex      = /\bsrc="(https?:\/\/[^"]+)"/g;
  const externalUrls  = new Set();
  let m;
  while ((m = srcRegex.exec(html)) !== null) {
    if (!weixinDomains.some(d => m[1].includes(d))) externalUrls.add(m[1]);
  }

  if (externalUrls.size === 0) {
    console.error('[图片] 正文中无需上传的外部图片');
    return html;
  }

  console.error(`[图片] 正文中发现 ${externalUrls.size} 张外部图片，开始上传到微信服务器...`);
  const urlMap = {};
  for (const url of externalUrls) {
    const weixinUrl = await uploadBodyImage(url, token);
    if (weixinUrl) urlMap[url] = weixinUrl;
  }

  let result = html;
  for (const [original, replacement] of Object.entries(urlMap)) {
    const escaped = original.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    result = result.replace(new RegExp(escaped, 'g'), replacement);
  }

  console.error(`[图片] ✅ 共替换 ${Object.keys(urlMap).length} 张图片 URL`);
  return result;
}

// ── 微信 API ───────────────────────────────────────────────────────────────

/** 获取微信 access_token */
async function getAccessToken(appId, appSecret) {
  const res  = await fetch(`${WECHAT_API}/token?grant_type=client_credential&appid=${appId}&secret=${appSecret}`);
  const data = await res.json();

  if (data.errcode && data.errcode !== 0) {
    if (data.errcode === 40164) {
      const ip = ((data.errmsg || '').match(/invalid ip\s+([\d.]+)/i) || [])[1] || '（见错误信息）';
      exitErr('40164', `IP 不在白名单。微信看到的实际 IP：${ip}\n请加入公众号后台 → 基础信息 → API IP 白名单后重试。\n原始错误：${data.errmsg}`);
    }
    exitErr(`wechat_token_${data.errcode}`, `获取 access_token 失败：${data.errmsg}（错误码 ${data.errcode}）`);
  }
  if (!data.access_token) exitErr('token_empty', `获取 access_token 返回异常：${JSON.stringify(data)}`);
  return data.access_token;
}

/** 推送草稿到微信草稿箱 */
async function pushDraft(token, title, author, htmlContent, thumbMediaId) {
  const article = {
    title,
    content:           htmlContent,
    thumb_media_id:    thumbMediaId,
    show_cover_pic:    1,
    need_open_comment: 0,
  };
  if (author) article.author = author;

  const res  = await fetch(`${WECHAT_API}/draft/add?access_token=${token}`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ articles: [article] }),
  });
  const data = await res.json();

  if (data.errcode && data.errcode !== 0) {
    const msg = data.errmsg || JSON.stringify(data);
    if (data.errcode === 40164) {
      const ip = (msg.match(/invalid ip\s+([\d.]+)/i) || [])[1] || '（见错误信息）';
      exitErr('40164', `IP 不在白名单。微信看到的实际 IP：${ip}\n请加入公众号后台 → 基础信息 → API IP 白名单后重试。\n原始错误：${msg}`);
    }
    exitErr(`wechat_draft_${data.errcode}`, `推送草稿失败：${msg}（错误码 ${data.errcode}）`);
  }
  return data.media_id;
}

// ── 主流程 ─────────────────────────────────────────────────────────────────
async function main() {
  const args = parseArgs(process.argv.slice(2));

  // 参数与环境变量校验
  if (!args.file) exitErr('missing_arg', '缺少 --file 参数（MD 文件路径）');
  if (!fs.existsSync(args.file)) exitErr('file_not_found', `MD 文件不存在：${args.file}`);

  const account  = process.env.ACCOUNT;
  const themeId  = process.env.THEME_ID;
  const apiBase  = (process.env.API_URL || 'https://feishu2weixin.maolai.cc').replace(/\/$/, '');
  const appId    = process.env.WECHAT_APP_ID;
  const appSecret = process.env.WECHAT_APP_SECRET;
  const defaultCover  = process.env.WECHAT_DEFAULT_COVER || FALLBACK_COVER;
  const defaultAuthor = process.env.AUTHOR_NAME || '';

  const missingEnv = [
    !account   && 'ACCOUNT（渲染服务注册账号）',
    !themeId   && 'THEME_ID（主题 ID）',
    !appId     && 'WECHAT_APP_ID',
    !appSecret && 'WECHAT_APP_SECRET',
  ].filter(Boolean);

  if (missingEnv.length) {
    exitErr('missing_env', '缺少必要环境变量，请检查 .env 文件：\n' + missingEnv.map(v => `  - ${v}`).join('\n'));
  }

  // ── 步骤1：IP 检查（无 --confirmed 时退出，提示用户确认白名单）──────────
  if (!args.confirmed) {
    let publicIp = '（查询失败，请手动查询）';
    try {
      const r = await fetch('https://api4.ipify.org');
      if (r.ok) publicIp = (await r.text()).trim();
    } catch {}

    console.log(JSON.stringify({
      success: false,
      error:   'need_confirm',
      ip:      publicIp,
      message: `请将以下 IP 加入公众号后台 → 基础信息 → API IP 白名单：${publicIp}\n⚠️  注意：微信实际看到的 IP 可能与上方不同（取决于网络路由），如收到 40164 错误，请将错误信息中的 IP 一并加入白名单。\n\n确认完成后，加上 --confirmed 重新运行。`,
    }, null, 2));
    process.exit(0);
  }

  // ── 步骤2：渲染 MD → 微信 HTML（内存中，不写本地文件）────────────────────
  console.error('[渲染] 正在调用渲染 API...');
  let html;
  try {
    const res = await fetch(`${apiBase}/api/skill`, {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Account':    account,
        'X-Theme-Id':   themeId,
      },
      body: JSON.stringify({ action: 'render', markdown: fs.readFileSync(args.file, 'utf-8') }),
    });

    if (!res.ok) exitErr('api_http_error', `渲染 API 返回 HTTP ${res.status}，请检查 API_URL 和网络连接`);

    const data = await res.json();
    if (!data.success) exitErr('api_error', `渲染 API 错误：${data.error || JSON.stringify(data)}`);
    html = data.html || '';
    if (!html) exitErr('empty_html', '渲染 API 返回空内容，请检查 ACCOUNT 和 THEME_ID 是否正确');
  } catch (e) {
    if (e.code === 'missing_env' || e.code === 'api_http_error') throw e;
    exitErr('render_failed', `渲染失败：${e.message}`);
  }
  console.error('[渲染] ✅ 完成');

  // ── 步骤3：确定标题、作者、封面 ─────────────────────────────────────────
  const mdContent = fs.readFileSync(args.file, 'utf-8');
  const mdDir     = path.dirname(path.resolve(args.file));

  const title  = args.title  || extractTitle(mdContent)  || path.basename(args.file, path.extname(args.file));
  const author = args.author || defaultAuthor;
  console.error(`[草稿] 标题：${title}`);
  console.error(`[草稿] 作者：${author || '（未设置）'}`);

  let coverSource;
  if (args.cover) {
    coverSource = args.cover;
    console.error(`[封面] 使用命令行指定封面：${coverSource}`);
  } else {
    const mdImg = extractFirstImage(mdContent);
    if (mdImg) {
      coverSource = mdImg;
      console.error(`[封面] 使用 MD 文件中第一张图片：${coverSource}`);
    } else {
      coverSource = defaultCover;
      console.error(`[封面] MD 无图片，使用兜底封面：${coverSource}`);
    }
  }

  // ── 步骤4：微信 API 操作 ─────────────────────────────────────────────────
  console.error('[微信] 正在获取 access_token...');
  const token = await getAccessToken(appId, appSecret);
  console.error('[微信] ✅ access_token 获取成功');

  const thumbMediaId  = await uploadCoverImage(coverSource, mdDir, token);
  const processedHtml = await uploadAndReplaceBodyImages(html, token);

  console.error('[草稿] 正在推送到微信草稿箱...');
  const draftMediaId = await pushDraft(token, title, author, processedHtml, thumbMediaId);
  console.error('[草稿] ✅ 推送成功');

  exitOk({
    success:  true,
    media_id: draftMediaId,
    title,
    message:  '草稿已推送成功，请前往公众号后台 → 草稿箱查看',
  });
}

main().catch(e => exitErr('unexpected', e.message));
