"""基于真实市场数据构建分类提示词 —— JSON 结构化输出。"""

from typing import Optional

CATEGORY_NAMES = {
    "市场热点": "01_市场热点",
    "新闻动态": "02_新闻动态",
    "IPO": "03_IPO",
    "投顾服务": "04_投顾服务",
    "投资者教育": "05_投资者教育",
    "每日精选": "06_每日精选",
}

BROKERAGE_SIGNATURE = (
    "🏦 广发证券 成都麓山大道营业部 | 您的身边理财管家\n"
    "📞 预约1对1专业投顾"
)


# ── 数据格式化工具 ──────────────────────────────────────────────

def _format_indices(indices: list) -> str:
    if not indices:
        return "（今日指数数据暂不可用）"
    lines = []
    for idx in indices:
        direction = "涨" if idx["change_pct"] > 0 else "跌" if idx["change_pct"] < 0 else "平"
        lines.append(f"  {idx['name']}：{idx['price']}（{direction}{idx['change_pct']:+.2f}%）")
    return "\n".join(lines)


def _format_sectors(sectors: list) -> str:
    if not sectors:
        return "（暂无板块数据）"
    return "\n".join(
        f"  - {s['name']}：{s['change_pct']:+.2f}%（领涨：{s.get('leading_stock', '')}）"
        for s in sectors
    )


def _format_breadth(breadth: dict) -> str:
    if not breadth:
        return "（暂无涨跌统计）"
    return f"上涨 {breadth['up']} 家 / 下跌 {breadth['down']} 家 / 平盘 {breadth.get('flat', 0)} 家"


def _format_news(news_data: Optional[dict]) -> str:
    if news_data is None:
        return "（今日新闻数据暂不可用）"
    items = []
    for n in news_data.get("all_news", []):
        items.append(f"  [{n.get('source', '')}] {n['title']}")
    # 兼容旧格式
    for n in news_data.get("eastmoney_news", []):
        items.append(f"  [证券时报/新华财经] {n['title']}")
    for n in news_data.get("cls_news", []):
        items.append(f"  [财联社] {n['title']}")
    if not items:
        return "（今日暂无重要快讯）"
    return "\n".join(items[:10])


def _format_ipo(ipo_data: Optional[dict]) -> str:
    if ipo_data is None or not ipo_data.get("new_stocks"):
        return "（近期暂无新股上市信息）"
    lines = []
    for s in ipo_data["new_stocks"]:
        lines.append(f"  - {s['name']}（{s['code']}）发行价 {s['ipo_price']}，上网发行日 {s['ipo_date']}")
    return "\n".join(lines)


# ── 基础上下文 ─────────────────────────────────────────────────

def build_base_context(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """构建共享的市场数据上下文。"""
    context = f"当前日期：{date_str}\n\n"
    context += "═══ 今日 A 股市场行情 ═══\n"
    context += _format_indices(market_data.get("indices", []) if market_data else []) + "\n\n"

    breadth = market_data.get("market_breadth") if market_data else None
    context += f"涨跌家数：{_format_breadth(breadth)}\n\n"

    context += "── 涨幅领先行业板块 ──\n"
    context += _format_sectors(market_data.get("top_sectors", []) if market_data else []) + "\n\n"
    context += "── 热门概念板块 ──\n"
    context += _format_sectors(market_data.get("top_concepts", []) if market_data else []) + "\n\n"

    context += "═══ 今日财经快讯 ═══\n"
    context += _format_news(news_data) + "\n\n"

    context += "═══ 近期 IPO 新股 ═══\n"
    context += _format_ipo(ipo_data) + "\n\n"

    return context


# ── JSON 输出规范（所有分类共用）────────────────────────────────

def _json_output_spec(config: dict) -> str:
    """生成 JSON 输出格式规范。"""
    brokerage = config.get("brokerage", {})
    name = brokerage.get("name", "广发证券")
    slogan = brokerage.get("slogan", "您的身边理财管家")
    contact = brokerage.get("contact", "预约1对1专业投顾")
    hashtags = " ".join(f"#{tag}" for tag in config.get("hashtags", []))

    return f"""
【输出格式要求 —— 极其重要】
你必须**只输出一个 JSON 对象**，不要有任何其他文字。JSON 格式如下：

{{
  "title": "标题字符串（≤20字）",
  "body": "正文字符串（约700字）",
  "image_texts": ["第1页文字", "第2页文字", "第3页文字"],
  "tags": ["#tag1", "#tag2", ...]
}}

**各字段详细规范：**

### title（标题）
- 字数：严格 ≤20 字
- 要求：有明确主题、有吸引力、让读者想点进来看
- 可以适当使用标点符号增强表达力
- 示例风格：「今日A股复盘：半导体为何集体爆发？」「A股尾盘异动，明天怎么看？」
- 不要用「标题：」前缀，直接写标题文字

### body（正文）
- 字数：约 700 字（中文），段落分明，行文流畅
- 风格：{config.get('tone', '专业、平实、亲切')}
- 受众：{config.get('audience', '有投资需求的年轻用户')}
- 重要：在正文合适位置自然地穿插使用小表情（如 📊 📈 💡 🔥 ⚡ ✅ ⚠️ 等），每条 2-4 个汉字可配一个表情，保持舒适不密集
- 内容规范：
  - 用公开信息视角表达，不可夸大宣传，不发布内幕或误导性建议
  - 语言真实自然，像是在和朋友聊天，避免官方套话
- 结尾格式（必须原样输出）：
  「{BROKERAGE_SIGNATURE}」
- 结尾之后不要再加其他内容

### image_texts（图片文字）
- 数量：1-3 页（根据内容量灵活决定，最少 1 页，最多 3 页）
- 每页字数：严格 80-200 字
- 说明：图片文字是正文的**精简浓缩版**，读者只看图片就能抓住文章核心
- 第 1 页：核心观点/问题/现象引入（吸引读者继续看下去）
- 第 2 页（如有）：展开分析/数据支撑/案例说明
- 第 3 页（如有）：总结观点/行动建议/互动引导
- 注意：图片文字要精简有力，去掉正文中的过渡语句，保留核心信息

### tags（话题标签）
- 数量：15 个左右（最少 10 个，最多 18 个）
- 每个 tag 以 # 开头
- 覆盖面：要有主题标签（如 #A股复盘 #今日看盘）、内容标签（如 #半导体 #新能源）、平台热门标签（如 #{' #'.join(config.get('hashtags', []))}）
- 多用小红书热门财经标签

### 通用合规要求
- 结尾必须包含风险提示精神（可在正文末尾自然带出）：「⚠️ 风险提示：市场有风险，投资需谨慎。本文仅为市场资讯分享，不构成任何投资建议。」
- 风险提示放在营业部署名之前
"""


# ── 各分类专属提示词 ────────────────────────────────────────────

def build_market_hotspot_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """市场热点 —— 今日走势 + 热门板块。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        "【今日写作任务：市场热点分析】\n\n"
        "你是一位券商营业部的专业内容运营，请根据上方真实市场数据，撰写一篇今日A股市场热点分析。\n\n"
        "写作要点：\n"
        "1. 开篇用1-2句话概括今日大盘整体走势（结合真实数据，涨跌如实写）\n"
        "2. 重点展开分析1-2个今日涨幅领先的板块/概念：\n"
        "   - 为什么涨？（政策利好？行业景气？资金流入？——用公开可查的逻辑解释）\n"
        "   - 这个板块后续怎么看？（给读者一个简明的判断框架）\n"
        "3. 结合涨跌家数等数据，给读者一个'今日市场温度'的直观感受\n"
        "4. 文中可自然地提及——如果想深入了解某个板块，可以联系我们营业部的专业投顾\n"
        "5. 语言轻松但不失专业，像是一个懂行的朋友在帮你复盘今天的盘面\n"
        f"{_json_output_spec(config)}"
    )


def build_news_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """新闻动态 —— 财经新闻解读。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        "【今日写作任务：财经新闻解读】\n\n"
        "你是一位券商营业部的专业内容运营，请根据上方今日财经快讯，撰写一篇新闻解读。\n\n"
        "写作要点：\n"
        "1. 从上方的财经快讯中挑选 2-3 条最重要的新闻作为主线\n"
        "2. 不要直接复制新闻标题，用你自己的话重新组织，每条新闻讲清楚：\n"
        "   - 发生了什么？（一句话）\n"
        "   - 为什么重要？（对市场/行业/普通投资者的影响）\n"
        "   - 投资者该怎么看？（给一个理性的分析视角）\n"
        "3. 如果多条新闻之间有关联（如政策+市场反应），要串起来讲，体现专业分析能力\n"
        "4. 避免制造焦虑，用理性、建设性的语气解读\n"
        "5. 可顺带提及——营业部投顾可以帮你过滤噪音，聚焦真正重要的信息\n"
        f"{_json_output_spec(config)}"
    )


def build_ipo_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """IPO —— 新股/打新。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    if ipo_data and ipo_data.get("new_stocks"):
        ipo_desc = "请根据上方的近期 IPO 新股信息展开写作。"
    else:
        ipo_desc = (
            "上方近期 IPO 信息暂缺。请围绕打新基础知识或近期 IPO 市场趋势（根据你的训练数据中"
            "公开信息，不要编造具体公司名称）来撰写。"
        )
    return (
        f"{ctx}\n"
        "【今日写作任务：IPO / 新股科普】\n\n"
        f"{ipo_desc}\n\n"
        "写作要点：\n"
        "1. 开篇介绍近期值得关注的新股动态或打新市场概况\n"
        "2. 用通俗语言解释一个和打新相关的知识点：\n"
        "   - 如什么是市盈率、发行价怎么定的、中签率是什么意思、注册制下打新有什么变化等\n"
        "3. 给新股投资者 2-3 条实用的注意事项或理性建议\n"
        "4. 提醒打新不是稳赚不赔，引导投资者理性参与\n"
        f"{_json_output_spec(config)}"
    )


def build_advisory_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """投顾服务 —— 营业部服务介绍。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        "【今日写作任务：投顾服务价值介绍】\n\n"
        "你是一位券商营业部的运营人员，请撰写一篇介绍投资顾问服务价值的内容。\n\n"
        "写作要点：\n"
        "1. 从普通投资者日常遇到的真实痛点切入，引起共鸣：\n"
        "   - 例如：信息太多不会筛选、看不懂财报、不知道什么时候该买该卖、\n"
        "     市场一跌就慌、听消息买股票总是被套……\n"
        "2. 自然地引出投顾服务的价值——不是推销，而是解决问题：\n"
        "   - 帮你梳理信息、建立投资体系、做你的'投资军师'\n"
        "   - 陪伴式服务，市场波动时有人商量\n"
        "3. 语气像朋友推荐好东西，亲切真诚\n"
        "4. 重要合规要求：不能承诺收益、不能保证赚钱、不能说'稳赚''必涨'等词汇\n"
        "5. 结尾自然地引导：想了解投顾服务可以私信或在评论区留言\n"
        f"{_json_output_spec(config)}"
    )


def build_education_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """投资者教育 —— 结合市场环境。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        "【今日写作任务：投资者教育】\n\n"
        "你是一位券商营业部的专业投教人员，请结合当前市场环境撰写一篇投资者教育内容。\n\n"
        "写作要点：\n"
        "1. 从一个常见的投资误区或近期市场典型现象切入：\n"
        "   - 如追涨杀跌、听消息炒股、不看基本面、满仓一只票、频繁交易等\n"
        "2. 用生活化的比喻帮助读者理解正确的投资理念：\n"
        "   - 例如：投资像种树不是赌博、资产配置像营养均衡的饮食等\n"
        "3. 给出具体可操作的建议（2-3条），不是空讲道理：\n"
        "   - 例如：定投怎么设、仓位怎么分、止损怎么定\n"
        "4. 可引用经典投资原则（巴菲特、芒格等）增强说服力，但要接地气\n"
        "5. 有温度，体现营业部对投资者的长期陪伴和关怀\n"
        f"{_json_output_spec(config)}"
    )


def build_daily_digest_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """每日精选 —— 一日精华汇总。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        "【今日写作任务：每日精选综合推送】\n\n"
        "这是今日最重要的综合推送，目标读者是时间有限但也想了解市场的人。\n\n"
        "写作要点：\n"
        "1. 开篇一句话总结今日市场核心特征（如「今日A股整体回暖，沪指小幅收涨，半导体板块领涨」）\n"
        "2. 正文分三个板块，用小标题+emoji分隔：\n"
        "   📊 今日盘面速览——指数+涨跌家数+最热板块（简短2-3句）\n"
        "   📰 今日必看新闻——最重要的1条财经新闻+一句话解读\n"
        "   💡 投资小贴士——今天分享一条简短实用的投资知识或心得\n"
        "3. 整体篇幅精炼，适合快速阅读，但要信息密度够\n"
        f"{_json_output_spec(config)}"
    )


# ── 分类映射 ────────────────────────────────────────────────────

PROMPT_BUILDERS = {
    "市场热点": build_market_hotspot_prompt,
    "新闻动态": build_news_prompt,
    "IPO": build_ipo_prompt,
    "投顾服务": build_advisory_prompt,
    "投资者教育": build_education_prompt,
    "每日精选": build_daily_digest_prompt,
}


def get_prompt(
    category: str,
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """根据分类获取对应的提示词。"""
    builder = PROMPT_BUILDERS.get(category)
    if builder is None:
        raise ValueError(f"未知内容分类：{category}")
    return builder(market_data, news_data, ipo_data, config, date_str)
