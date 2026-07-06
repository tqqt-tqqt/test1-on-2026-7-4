"""基于真实市场数据构建分类提示词。"""

from typing import Optional


CATEGORY_NAMES = {
    "市场热点": "01_市场热点",
    "新闻动态": "02_新闻动态",
    "IPO": "03_IPO",
    "投顾服务": "04_投顾服务",
    "投资者教育": "05_投资者教育",
    "每日精选": "06_每日精选",
}

CATEGORY_EMOJI = {
    "市场热点": "📈",
    "新闻动态": "📰",
    "IPO": "🚀",
    "投顾服务": "💼",
    "投资者教育": "📚",
    "每日精选": "🌟",
}


def _format_indices(indices: list) -> str:
    if not indices:
        return "（今日指数数据暂不可用）"
    lines = []
    for idx in indices:
        direction = "📈" if idx["change_pct"] > 0 else "📉" if idx["change_pct"] < 0 else "➡️"
        lines.append(
            f"  {direction} {idx['name']}：{idx['price']}（{idx['change_pct']:+.2f}%）"
        )
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
    total = breadth["up"] + breadth["down"] + breadth["flat"]
    return (
        f"上涨 {breadth['up']} 家 / 下跌 {breadth['down']} 家 / 平盘 {breadth['flat']} 家"
        f"（共 {total} 只个股）"
    )


def _format_gainers(gainers: list) -> str:
    if not gainers:
        return "（暂无涨幅榜数据）"
    return "\n".join(
        f"  - {g['name']}（{g['code']}）：{g['change_pct']:+.2f}%"
        for g in gainers
    )


def _format_news(news_data: Optional[dict]) -> str:
    """格式化新闻摘要。"""
    if news_data is None:
        return "（今日新闻数据暂不可用）"
    items = []
    for n in news_data.get("eastmoney_news", []):
        items.append(f"  [东方财富] {n['title']}")
    for n in news_data.get("cls_news", []):
        items.append(f"  [财联社] {n['title']}")
    if not items:
        return "（今日暂无重要快讯）"
    return "\n".join(items[:8])


def _format_ipo(ipo_data: Optional[dict]) -> str:
    """格式化 IPO 新股信息。"""
    if ipo_data is None or not ipo_data.get("new_stocks"):
        return "（近期暂无新股上市信息）"
    lines = []
    for s in ipo_data["new_stocks"]:
        lines.append(f"  - {s['name']}（{s['code']}）发行价 {s['ipo_price']}，上网发行日 {s['ipo_date']}")
    return "\n".join(lines)


def build_base_context(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """构建共享的市场数据上下文，各分类提示词复用。"""
    hashtags = " ".join(f"#{tag}" for tag in config.get("hashtags", []))

    context = f"当前日期：{date_str}\n\n"

    # 指数行情
    context += "═══ 今日 A 股市场行情 ═══\n"
    context += _format_indices(market_data.get("indices", []) if market_data else []) + "\n\n"

    # 涨跌家数
    breadth = market_data.get("market_breadth") if market_data else None
    context += f"涨跌家数：{_format_breadth(breadth)}\n\n"

    # 热点板块
    context += "── 涨幅领先行业板块 ──\n"
    context += _format_sectors(market_data.get("top_sectors", []) if market_data else []) + "\n\n"
    context += "── 涨幅领先概念板块 ──\n"
    context += _format_sectors(market_data.get("top_concepts", []) if market_data else []) + "\n\n"

    # 涨幅榜
    context += "── 今日涨幅榜 ──\n"
    context += _format_gainers(market_data.get("top_gainers", []) if market_data else []) + "\n\n"

    # 新闻
    context += "═══ 今日财经快讯 ═══\n"
    context += _format_news(news_data) + "\n\n"

    # IPO
    context += "═══ 近期 IPO 新股 ═══\n"
    context += _format_ipo(ipo_data) + "\n\n"

    return context


def build_common_requirements(config: dict) -> str:
    """各分类提示词的通用结尾要求。"""
    hashtags = " ".join(f"#{tag}" for tag in config.get("hashtags", []))
    return (
        f"风格基调：{config.get('tone', '专业、平实、亲切')}\n"
        f"目标受众：{config.get('audience', '有投资需求的年轻用户')}\n"
        f"字数要求：{config.get('length', '150-220字')}\n"
        "重要规范：\n"
        "  - 用公开信息视角表达，不可夸大宣传，不发布内幕或误导性建议\n"
        "  - 语言真实自然，像是在和读者聊天，避免官方套话\n"
        "  - 使用适当 emoji 增加可读性，但不过度\n"
        "  - 结尾必须包含完整风险提示：「⚠️ 风险提示：市场有风险，投资需谨慎。"
        "本文仅为市场资讯分享，不构成任何投资建议。」\n"
        "  - 文末附带一条简短的互动引导（如：评论区聊聊你的看法吧！）\n"
        f"  - 文末带上话题标签：{hashtags}\n"
        "  - 输出格式：直接输出小红书正文内容，不需要标题前缀「标题：」之类"
    )


# ── 各分类专属提示词构建 ──


def build_market_hotspot_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """市场热点 —— 聚焦今日走势与热门板块。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        '【今日任务：撰写一篇「市场热点」方向的小红书文案】\n\n'
        '以券商营业部运营人员的口吻，做好以下要点：\n'
        '  1. 用 1-2 句话概括今日大盘走势（看数据说话，涨了就写涨，跌了就写跌），语言轻松不沉重\n'
        '  2. 重点分析 1-2 个今日涨幅领先的板块/概念，用通俗语言解释为什么涨\n'
        '     （例如：政策利好、行业景气度回升、资金流入等公开可查的逻辑）\n'
        '  3. 结合数据给读者一个「今日市场温度」的直观感受\n'
        '  4. 文中可顺带一句营业部服务引导，如「想了解更多板块分析可以联系我们」\n\n'
        f"{build_common_requirements(config)}"
    )


def build_news_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """新闻动态 —— 梳理今日重要财经新闻。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        '【今日任务：撰写一篇「新闻动态」方向的小红书文案】\n\n'
        '以券商营业部运营人员的口吻，做好以下要点：\n'
        '  1. 从上方的今日财经快讯中挑选 2-3 条最重要的新闻\n'
        '  2. 用通俗语言解读新闻对普通投资者的影响（避免直接复制新闻标题）\n'
        "  3. 如果新闻与市场走势有明显联动，点出这个逻辑\n"
        '  4. 帮助读者理解「这条新闻为什么值得关注」\n\n'
        f"{build_common_requirements(config)}"
    )


def build_ipo_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """IPO —— 新股/打新相关内容。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    if ipo_data and ipo_data.get("new_stocks"):
        ipo_desc = "请根据上方的近期 IPO 新股信息撰写文案。"
    else:
        ipo_desc = (
            "上方近期 IPO 信息暂缺，请以通用打新知识或近期 IPO 市场趋势（根据你的训练数据中"
            "公开信息）来撰写。"
        )
    return (
        f"{ctx}\n"
        '【今日任务：撰写一篇「IPO / 新股」方向的小红书文案】\n\n'
        f"{ipo_desc}\n"
        "要点：\n"
        "  1. 介绍近期值得关注的新股/IPO 动态\n"
        "  2. 用通俗方式解释打新规则或新股投资注意事项\n"
        "  3. 引导投资者理性参与新股申购\n\n"
        f"{build_common_requirements(config)}"
    )


def build_advisory_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """投顾服务 —— 介绍营业部投顾服务和价值。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        '【今日任务：撰写一篇「投顾服务介绍」方向的小红书文案】\n\n'
        "以券商营业部运营人员的口吻，撰写一篇介绍投资顾问服务价值的文案。要点：\n"
        "  1. 从普通投资者的痛点切入（信息太多不会筛选、不会看财报、不知何时买卖等）\n"
        "  2. 自然引入投顾服务的价值：专业解读、个性化建议、陪伴式服务\n"
        "  3. 语气要亲切，像朋友推荐好东西，不要像推销\n"
        "  4. 不能承诺收益，不能保证赚钱，必须合规\n"
        "  5. 结尾引导：想了解投顾服务可以私信/留言\n\n"
        f"{build_common_requirements(config)}"
    )


def build_education_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """投资者教育 —— 结合当前市场环境做投教。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        '【今日任务：撰写一篇「投资者教育」方向的小红书文案】\n\n'
        "以券商营业部运营人员的口吻，结合当前市场环境撰写一篇投资者教育内容。要点：\n"
        "  1. 从当下市场的一个常见误区或投资者容易犯的错误切入\n"
        "     （如追涨杀跌、听消息买股票、不看基本面等）\n"
        "  2. 给出正确的投资理念和方法（资产配置、长期投资、分散风险等）\n"
        "  3. 内容要接地气，用生活化的比喻帮助读者理解\n"
        "  4. 既要讲知识，也要有温度，体现营业部对投资者的关怀\n"
        "  5. 可引用经典投资名言或巴菲特的简单原则来增强说服力\n\n"
        f"{build_common_requirements(config)}"
    )


def build_daily_digest_prompt(
    market_data: Optional[dict],
    news_data: Optional[dict],
    ipo_data: Optional[dict],
    config: dict,
    date_str: str,
) -> str:
    """每日精选 —— 综合一日市场精华。"""
    ctx = build_base_context(market_data, news_data, ipo_data, config, date_str)
    return (
        f"{ctx}\n"
        '【今日任务：撰写一篇「每日精选」方向的小红书综合文案】\n\n'
        '这是今日最重要的综合推送，涵盖市场概览 + 热点快评 + 一个小知识。要点：\n'
        '  1. 开篇用一句话总结今日市场（如「今日A股整体偏暖，沪指小幅收涨」之类）\n'
        "  2. 分成 3 个小段落，用 emoji 分隔：\n"
        "     📊 今日盘面：指数+涨跌家数+最热板块（1-2句）\n"
        "     📰 值得关注：1条最重要的财经新闻解读（1-2句）\n"
        "     💡 投资小贴士：分享一条简短有用的投资知识或提醒\n"
        "  3. 整体篇幅精炼，适合读者快速浏览获取一天精华\n\n"
        f"{build_common_requirements(config)}"
    )


# ── 分类 → 提示词构建函数 映射 ──

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
