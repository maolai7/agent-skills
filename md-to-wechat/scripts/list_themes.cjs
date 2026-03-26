/**
 * list_themes.cjs - 辅助工具：列出账号下所有主题 ID
 *
 * 作用：首次配置时，查询你在 feishu2weixin 保存的所有主题及其 ID，
 *       将目标主题的 ID 填入 .env 的 THEME_ID 字段。
 *
 * 用法：
 *   node list_themes.cjs
 *
 * 依赖：Node.js 18+，零 npm 依赖
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

// ── 主流程 ─────────────────────────────────────────────────────────────────
async function main() {
  const account = process.env.ACCOUNT;
  const apiBase = (process.env.API_URL || 'https://feishu2weixin.maolai.cc').replace(/\/$/, '');

  if (!account) {
    console.error(JSON.stringify({
      success: false,
      error:   'missing_env',
      message: '缺少 ACCOUNT，请在 .env 文件中填写注册账号（邮箱或手机号）',
    }, null, 2));
    process.exit(1);
  }

  console.error(`[主题列表] 正在查询账号 ${account} 的主题...`);

  let data;
  try {
    const res = await fetch(`${apiBase}/api/skill`, {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Account':    account,
      },
      body: JSON.stringify({ action: 'list_themes' }),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const json = await res.json();
    if (!json.success) throw new Error(json.error || JSON.stringify(json));

    data = json;
  } catch (e) {
    console.error(JSON.stringify({
      success: false,
      error:   'api_error',
      message: `查询失败：${e.message}`,
    }, null, 2));
    process.exit(1);
  }

  if (!data.themes || data.themes.length === 0) {
    console.log(JSON.stringify({
      success: true,
      count:   0,
      themes:  [],
      message: '该账号暂无保存的主题，请先在网站创建并保存一个主题',
    }, null, 2));
    return;
  }

  // 格式化输出，方便阅读
  console.log('\n主题列表：\n');
  data.themes.forEach((t, i) => {
    console.log(`  ${i + 1}. ${t.name}`);
    console.log(`     ID：${t.id}`);
    console.log('');
  });
  console.log(`共 ${data.count} 个主题。将目标主题 ID 填入 .env 的 THEME_ID 字段。\n`);
}

main().catch(e => {
  console.error(JSON.stringify({ success: false, error: 'unexpected', message: e.message }, null, 2));
  process.exit(1);
});
