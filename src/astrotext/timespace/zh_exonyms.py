"""Chinese exonyms for world cities — a NAME-MAPPING supplement.

The GeoNames cities dump carries Chinese alternate names for many cities
(Beijing, Tokyo, Moscow resolve directly) but not all (New York's zh name
lives only in the huge alternateNamesV2 dump).  This table maps common
Chinese exonyms to (english_query, country_filter) pairs; coordinates and
timezones STILL come from the gazetteer — no geographic data is hardcoded,
so every entry is machine-verified by tests (each must resolve).

Curation rule: only unambiguous, extremely common exonyms.  Ambiguous ones
(剑桥, 圣地亚哥 without country...) are either country-pinned or omitted.
"""
from __future__ import annotations

__all__ = ["ZH_EXONYMS"]

#: zh name -> (gazetteer query, country code or None)
ZH_EXONYMS: dict[str, tuple[str, str | None]] = {
    # North America
    "纽约": ("New York City", "US"), "洛杉矶": ("Los Angeles", "US"),
    "芝加哥": ("Chicago", "US"), "休斯顿": ("Houston", "US"),
    "费城": ("Philadelphia", "US"), "波士顿": ("Boston", "US"),
    "西雅图": ("Seattle", "US"), "迈阿密": ("Miami", "US"),
    "亚特兰大": ("Atlanta", "US"), "底特律": ("Detroit", "US"),
    "达拉斯": ("Dallas", "US"), "丹佛": ("Denver", "US"),
    "拉斯维加斯": ("Las Vegas", "US"), "圣迭戈": ("San Diego", "US"),
    "圣地亚哥(美国)": ("San Diego", "US"), "凤凰城": ("Phoenix", "US"),
    "奥斯汀": ("Austin", "US"), "檀香山": ("Honolulu", "US"),
    "安克雷奇": ("Anchorage", "US"), "圣何塞": ("San Jose", "US"),
    "多伦多": ("Toronto", "CA"), "温哥华": ("Vancouver", "CA"),
    "蒙特利尔": ("Montreal", "CA"), "渥太华": ("Ottawa", "CA"),
    "墨西哥城": ("Mexico City", "MX"),
    # Oceania
    "悉尼": ("Sydney", "AU"), "墨尔本": ("Melbourne", "AU"),
    "布里斯班": ("Brisbane", "AU"), "珀斯": ("Perth", "AU"),
    "堪培拉": ("Canberra", "AU"), "奥克兰(新西兰)": ("Auckland", "NZ"),
    "惠灵顿": ("Wellington", "NZ"),
    # Asia
    "新加坡": ("Singapore", "SG"), "吉隆坡": ("Kuala Lumpur", "MY"),
    "曼谷": ("Bangkok", "TH"), "雅加达": ("Jakarta", "ID"),
    "马尼拉": ("Manila", "PH"), "河内": ("Hanoi", "VN"),
    "胡志明市": ("Ho Chi Minh City", "VN"), "首尔": ("Seoul", "KR"),
    "釜山": ("Busan", "KR"), "平壤": ("Pyongyang", "KP"),
    "大阪": ("Osaka", "JP"), "京都": ("Kyoto", "JP"),
    "名古屋": ("Nagoya", "JP"), "横滨": ("Yokohama", "JP"),
    "神户": ("Kobe", "JP"), "福冈": ("Fukuoka", "JP"),
    "札幌": ("Sapporo", "JP"), "新德里": ("New Delhi", "IN"),
    "孟买": ("Mumbai", "IN"), "加尔各答": ("Kolkata", "IN"),
    "班加罗尔": ("Bengaluru", "IN"), "金奈": ("Chennai", "IN"),
    "迪拜": ("Dubai", "AE"), "阿布扎比": ("Abu Dhabi", "AE"),
    "利雅得": ("Riyadh", "SA"), "特拉维夫": ("Tel Aviv", "IL"),
    "耶路撒冷": ("Jerusalem", "IL"), "伊斯坦布尔": ("Istanbul", "TR"),
    "德黑兰": ("Tehran", "IR"), "卡拉奇": ("Karachi", "PK"),
    # Europe
    "伦敦": ("London", "GB"), "巴黎": ("Paris", "FR"),
    "柏林": ("Berlin", "DE"), "慕尼黑": ("Munich", "DE"),
    "法兰克福": ("Frankfurt am Main", "DE"), "汉堡": ("Hamburg", "DE"),
    "科隆": ("Cologne", "DE"), "罗马": ("Rome", "IT"),
    "米兰": ("Milan", "IT"), "威尼斯": ("Venice", "IT"),
    "佛罗伦萨": ("Florence", "IT"), "那不勒斯": ("Naples", "IT"),
    "马德里": ("Madrid", "ES"), "巴塞罗那": ("Barcelona", "ES"),
    "里斯本": ("Lisbon", "PT"), "阿姆斯特丹": ("Amsterdam", "NL"),
    "布鲁塞尔": ("Brussels", "BE"), "苏黎世": ("Zurich", "CH"),
    "日内瓦": ("Geneva", "CH"), "维也纳": ("Vienna", "AT"),
    "布拉格": ("Prague", "CZ"), "华沙": ("Warsaw", "PL"),
    "布达佩斯": ("Budapest", "HU"), "斯德哥尔摩": ("Stockholm", "SE"),
    "哥本哈根": ("Copenhagen", "DK"), "奥斯陆": ("Oslo", "NO"),
    "赫尔辛基": ("Helsinki", "FI"), "都柏林": ("Dublin", "IE"),
    "爱丁堡": ("Edinburgh", "GB"), "曼彻斯特": ("Manchester", "GB"),
    "利物浦": ("Liverpool", "GB"), "牛津": ("Oxford", "GB"),
    "雅典": ("Athens", "GR"), "圣彼得堡": ("Saint Petersburg", "RU"),
    "基辅": ("Kyiv", "UA"),
    # South America & Africa
    "圣保罗": ("Sao Paulo", "BR"), "里约热内卢": ("Rio de Janeiro", "BR"),
    "布宜诺斯艾利斯": ("Buenos Aires", "AR"), "圣地亚哥(智利)": ("Santiago", "CL"),
    "利马": ("Lima", "PE"), "波哥大": ("Bogota", "CO"),
    "开罗": ("Cairo", "EG"), "开普敦": ("Cape Town", "ZA"),
    "约翰内斯堡": ("Johannesburg", "ZA"), "内罗毕": ("Nairobi", "KE"),
    "拉各斯": ("Lagos", "NG"), "卡萨布兰卡": ("Casablanca", "MA"),
}
