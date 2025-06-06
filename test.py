import streamlit as st
import requests, httpx, re
from bs4 import BeautifulSoup
from datetime import datetime, date, time as dtime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

# === 키워드 그룹 정의 ===
keyword_groups = {
    '시경': ['서울경찰청'],
    '본청': ['경찰청'],
    '종혜북': [
        '종로', '종암', '성북', '고려대', '참여연대', '혜화', '동대문', '중랑',
        '성균관대', '한국외대', '서울시립대', '경희대', '경실련', '서울대병원',
        '노원', '강북', '도봉', '북부지법', '북부지검', '상계백병원', '국가인권위원회'
    ],
    '마포중부': [
        '마포', '서대문', '서부', '은평', '서부지검', '서부지법', '연세대',
        '신촌세브란스병원', '군인권센터', '중부', '남대문', '용산', '동국대',
        '숙명여대', '순천향대병원'
    ],
    '영등포관악': [
        '영등포', '양천', '구로', '강서', '남부지검', '남부지법', '여의도성모병원',
        '고대구로병원', '관악', '금천', '동작', '방배', '서울대', '중앙대', '숭실대', '보라매병원'
    ],
    '강남광진': [
        '강남', '서초', '수서', '송파', '강동', '삼성의료원', '현대아산병원',
        '강남세브란스병원', '광진', '성동', '동부지검', '동부지법', '한양대',
        '건국대', '세종대'
    ]
}

# === Streamlit UI ===
st.set_page_config(page_title="뉴스 키워드 수집기", layout="wide")
st.title("📰 뉴스 키워드 수집기 (통합버전)")

mode = st.radio("기능 선택", ["[단독] 기사 수집기", "연합뉴스·뉴시스 기사 수집기"])

now = datetime.now(ZoneInfo("Asia/Seoul"))
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("시작 날짜", value=now.date())
    start_time = st.time_input("시작 시간", value=dtime(0, 0))
with col2:
    end_date = st.date_input("종료 날짜", value=now.date())
    end_time = st.time_input("종료 시간", value=dtime(now.hour, now.minute))

start_dt = datetime.combine(start_date, start_time).replace(tzinfo=ZoneInfo("Asia/Seoul"))
end_dt = datetime.combine(end_date, end_time).replace(tzinfo=ZoneInfo("Asia/Seoul"))

selected_groups = st.multiselect("키워드 그룹 선택", list(keyword_groups.keys()), default=["시경", "종혜북"])
selected_keywords = [kw for group in selected_groups for kw in keyword_groups[group]]

# === 공통 함수 ===
def highlight_keywords(text, keywords):
    for kw in keywords:
        text = re.sub(f"({re.escape(kw)})", r'<mark style="background-color: #fffb91">\1</mark>', text)
    return text

# === [단독] 기사 수집기 ===
def parse_pubdate(pubdate_str):
    try:
        return datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %z")
    except:
        return None

def extract_article_text(url):
    try:
        if "n.news.naver.com" not in url:
            return None
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(html.text, "html.parser")
        content_div = soup.find("div", id="newsct_article")
        return content_div.get_text(separator="\n", strip=True) if content_div else None
    except:
        return None

def extract_media_name(url):
    try:
        domain = url.split("//")[-1].split("/")[0]
        parts = domain.split(".")
        composite_key = f"{parts[-3]}.{parts[-2]}" if len(parts) >= 3 else parts[0]
        return {
            "chosun": "조선", "joongang": "중앙", "donga": "동아", "hani": "한겨레",
            "khan": "경향", "hankookilbo": "한국", "segye": "세계", "seoul": "서울",
            "kmib": "국민", "munhwa": "문화", "kbs": "KBS", "sbs": "SBS",
            "imnews": "MBC", "jtbc": "JTBC", "ichannela": "채널A", "tvchosun": "TV조선",
            "mk": "매경", "sedaily": "서경", "hankyung": "한경", "news1": "뉴스1",
            "newsis": "뉴시스", "yna": "연합", "mt": "머투", "weekly": "주간조선",
            "biz.chosun": "조선비즈", "fnnews": "파뉴"
        }.get(composite_key, composite_key.upper())
    except:
        return "[매체추출실패]"

def fetch_and_filter(item, start_dt, end_dt, selected_keywords, use_keyword_filter):
    title = BeautifulSoup(item["title"], "html.parser").get_text()
    if "[단독]" not in title:
        return None
    pub_dt = parse_pubdate(item.get("pubDate"))
    if not pub_dt or not (start_dt <= pub_dt <= end_dt):
        return None
    link = item.get("link")
    if not link or "n.news.naver.com" not in link:
        return None
    body = extract_article_text(link)
    if not body:
        return None
    matched_keywords = [kw for kw in selected_keywords if kw in body] if use_keyword_filter else []
    if use_keyword_filter and not matched_keywords:
        return None
    highlighted_body = highlight_keywords(body, matched_keywords).replace("\n", "<br><br>")
    media = extract_media_name(item.get("originallink", ""))
    return {
        "매체": media,
        "제목": title,
        "날짜": pub_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "본문": body,
        "필터일치": ", ".join(matched_keywords),
        "링크": link,
        "하이라이트": highlighted_body
    }

def run_dandok():
    use_filter = st.checkbox("📎 키워드 포함 기사만 필터링", value=True)
    if st.button("✅ [단독] 뉴스 수집 시작"):
        client_id = "R7Q2OeVNhj8wZtNNFBwL"
        client_secret = "49E810CBKY"
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret
        }
        st.info("수집 중...")
        all_articles = []
        for start in range(1, 1001, 100):
            res = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                headers=headers,
                params={"query": "[단독]", "display": 100, "start": start, "sort": "date"},
                timeout=5
            )
            if res.status_code != 200: break
            items = res.json().get("items", [])
            with ThreadPoolExecutor(max_workers=10) as ex:
                futures = [ex.submit(fetch_and_filter, item, start_dt, end_dt, selected_keywords, use_filter) for item in items]
                for f in as_completed(futures):
                    result = f.result()
                    if result:
                        all_articles.append(result)
                        st.markdown(f"**△{result['매체']}/{result['제목']}**")
                        st.caption(result["날짜"])
                        st.markdown(f"🔗 [원문 보기]({result['링크']})")
                        if result["필터일치"]:
                            st.write(f"**일치 키워드:** {result['필터일치']}")
                        st.markdown(f"- {result['하이라이트']}", unsafe_allow_html=True)
        if all_articles:
            st.subheader("📋 복사용 텍스트")
            text = ""
            for art in all_articles:
                clean_title = re.sub(r"\[단독\]|\(단독\)|【단독】|ⓧ단독|^단독\s*[:-]?", "", art['제목']).strip()
                text += f"△{art['매체']}/{clean_title}\n- {art['본문']}\n\n"
            st.code(text.strip(), language="markdown")

# === 연합뉴스/뉴시스 수집기 ===
def get_article_content(url, selector):
    try:
        res = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5.0)
        soup = BeautifulSoup(res.text, "html.parser")
        el = soup.select_one(selector)
        return el.get_text(separator="\n", strip=True) if el else ""
    except:
        return ""

def fetch_news_articles(source_name, url_template, list_selector, title_selector, time_selector, time_format, content_selector, domain_prefix=""):
    articles, page = [], 1
    while True:
        url = url_template.format(page=page)
        res = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(list_selector)
        if not items:
            break
        for item in items:
            title_tag = item.select_one(title_selector)
            time_tag = item.select_one(time_selector)
            if not (title_tag and time_tag): continue
            try:
                dt = datetime.strptime(time_tag.text.strip(), time_format).replace(tzinfo=ZoneInfo("Asia/Seoul"))
            except:
                continue
            if dt < start_dt:
                return articles
            if dt <= end_dt:
                href = title_tag.get("href")
                full_url = domain_prefix + href if domain_prefix else href
                articles.append({
                    "source": source_name,
                    "title": title_tag.get_text(strip=True),
                    "datetime": dt,
                    "url": full_url
                })
        page += 1
    return articles

def run_newsis_yonhap():
    if st.button("📥 연합뉴스·뉴시스 기사 수집 시작"):
        collected = []
        newsis = fetch_news_articles(
            "뉴시스", "https://www.newsis.com/realnews/?cid=realnews&day=today&page={page}",
            "ul.articleList2 > li", "p.tit > a", "p.time",
            "%Y.%m.%d %H:%M:%S", "div.viewer", "https://www.newsis.com"
        )
        yonhap = fetch_news_articles(
            "연합뉴스", "https://www.yna.co.kr/news/{page}?site=navi_latest_depth01",
            "ul.list01 > li[data-cid]", ".title01", ".txt-time",
            "%Y-%m-%d %H:%M", "div.story-news.article", "https://www.yna.co.kr"
        )
        collected = newsis + yonhap
        st.success(f"✅ {len(collected)}건 수집됨")
        if collected:
            st.subheader("📋 복사용 텍스트")
            text_block = ""
            for art in collected:
                content = get_article_content(art["url"], "div.viewer" if art["source"] == "뉴시스" else "div.story-news.article")
                if any(kw in content for kw in selected_keywords):
                    st.markdown(f"**[{art['title']}]({art['url']})**")
                    st.caption(f"{art['datetime'].strftime('%Y-%m-%d %H:%M')} | {art['source']}")
                    st.markdown(highlight_keywords(content, selected_keywords).replace("\n", "<br>"), unsafe_allow_html=True)
                    st.markdown("---")
                    text_block += f"△{art['title']}\n- {content.strip()[:300]}\n\n"
            st.code(text_block.strip(), language="markdown")

# === 실행 ===
if mode == "[단독] 기사 수집기":
    run_dandok()
else:
    run_newsis_yonhap()
