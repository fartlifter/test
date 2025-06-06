import streamlit as st
import requests
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, date, time as dtime
from zoneinfo import ZoneInfo
import time as t
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 키워드 그룹 공통 정의 ---
keyword_groups = {
    '시경': ['서울경찰청'],
    '본청': ['경찰청'],
    '종혜북': ['종로', '종암', '성북', '고려대', '참여연대', '혜화', '동대문', '중랑',
            '성균관대', '한국외대', '서울시립대', '경희대', '경실련', '서울대병원',
            '노원', '강북', '도봉', '북부지법', '북부지검', '상계백병원', '국가인권위원회'],
    '마포중부': ['마포', '서대문', '서부', '은평', '서부지검', '서부지법', '연세대',
             '신촌세브란스병원', '군인권센터', '중부', '남대문', '용산', '동국대',
             '숙명여대', '순천향대병원'],
    '영등포관악': ['영등포', '양천', '구로', '강서', '남부지검', '남부지법', '여의도성모병원',
              '고대구로병원', '관악', '금천', '동작', '방배', '서울대', '중앙대', '숭실대', '보라매병원'],
    '강남광진': ['강남', '서초', '수서', '송파', '강동', '삼성의료원', '현대아산병원',
             '강남세브란스병원', '광진', '성동', '동부지검', '동부지법', '한양대', '건국대', '세종대']
}

# --- 날짜/시간 선택 UI ---
now = datetime.now(ZoneInfo("Asia/Seoul"))
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("시작 날짜", value=now.date())
    start_time = st.time_input("시작 시각", value=dtime(0, 0))
with col2:
    end_date = st.date_input("종료 날짜", value=now.date())
    end_time = st.time_input("종료 시각", value=dtime(now.hour, now.minute))

start_dt = datetime.combine(start_date, start_time).replace(tzinfo=ZoneInfo("Asia/Seoul"))
end_dt = datetime.combine(end_date, end_time).replace(tzinfo=ZoneInfo("Asia/Seoul"))

# --- 키워드 선택 ---
group_labels = list(keyword_groups.keys())
selected_groups = st.multiselect("📚 지역 키워드 그룹", group_labels, default=['시경', '종혜북'])
selected_keywords = [kw for group in selected_groups for kw in keyword_groups[group]]
use_keyword_filter = st.checkbox("📎 키워드 포함 기사만 필터링", value=True)

# --- 실행 기능 선택 ---
st.markdown("## 🔧 실행할 수집기를 선택하세요")
options = st.multiselect("수집기 선택", ["[단독] 뉴스 수집기", "연합뉴스·뉴시스 수집기"])

# --- 단독 기사 수집 함수 ---
def fetch_dandok_news():
    st.subheader("📥 [단독] 뉴스 수집")
    client_id = "R7Q2OeVNhj8wZtNNFBwL"
    client_secret = "49E810CBKY"
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    seen_links = set()
    results = []

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
            key = parts[-3] if len(parts) >= 3 else parts[0]
            media_map = {"chosun": "조선", "joongang": "중앙", "donga": "동아", "hani": "한겨레", "khan": "경향",
                         "segye": "세계", "yna": "연합", "newsis": "뉴시스", "kmib": "국민", "kbs": "KBS", "sbs": "SBS"}
            return media_map.get(key, key.upper())
        except:
            return "UNKNOWN"

    with st.spinner("🔍 [단독] 뉴스 수집 중..."):
        for start_index in range(1, 1001, 100):
            params = {"query": "[단독]", "sort": "date", "display": 100, "start": start_index}
            res = requests.get("https://openapi.naver.com/v1/search/news.json", headers=headers, params=params)
            if res.status_code != 200: break
            items = res.json().get("items", [])
            if not items: break

            for item in items:
                title = BeautifulSoup(item["title"], "html.parser").get_text()
                if "[단독]" not in title: continue
                pub_dt = parse_pubdate(item.get("pubDate", ""))
                if not pub_dt or not (start_dt <= pub_dt <= end_dt): continue
                link = item.get("link")
                body = extract_article_text(link)
                if not body: continue
                matched = [kw for kw in selected_keywords if kw in body] if use_keyword_filter else []
                if use_keyword_filter and not matched: continue
                highlight = re.sub(f"({'|'.join(map(re.escape, matched))})", r"<mark>\1</mark>", body)
                media = extract_media_name(item.get("originallink", ""))
                results.append({
                    "title": title, "body": body, "highlight": highlight.replace("\n", "<br><br>"),
                    "media": media, "link": link, "date": pub_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "matched": matched
                })

    for row in results:
        st.markdown(f"△{row['media']}/{row['title']}")
        st.caption(row['date'])
        st.markdown(f"[원문 보기]({row['link']})")
        if row['matched']:
            st.write(f"**일치 키워드:** {', '.join(row['matched'])}**")
        st.markdown(f"- {row['highlight']}", unsafe_allow_html=True)

    return results

# --- 연합뉴스/뉴시스 기사 수집 함수 ---
def fetch_press_news():
    st.subheader("📥 연합뉴스 · 뉴시스 기사 수집")
    collected = []

    def highlight_keywords(text, keywords):
        for kw in keywords:
            text = re.sub(f"({re.escape(kw)})", r'<mark style="background-color: #fffb91">\1</mark>', text)
        return text.replace("\n", "<br>")

    def get_content(url, selector):
        try:
            res = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5.0)
            soup = BeautifulSoup(res.text, "html.parser")
            content = soup.select_one(selector)
            return content.get_text(separator="\n", strip=True) if content else ""
        except:
            return ""

    def fetch_articles(article_list, selector):
        results = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(get_content, a['url'], selector): a for a in article_list}
            for future in as_completed(futures):
                art = futures[future]
                try:
                    content = future.result()
                    if any(kw in content for kw in selected_keywords):
                        art['content'] = content
                        results.append(art)
                except:
                    continue
        return results

    # 연합뉴스
    page, yonhap_list = 1, []
    while True:
        url = f"https://www.yna.co.kr/news/{page}?site=navi_latest_depth01"
        res = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5.0)
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select("ul.list01 > li[data-cid]")
        if not items: break
        for item in items:
            cid = item.get("data-cid")
            title_tag = item.select_one(".title01")
            time_tag = item.select_one(".txt-time")
            if not (cid and title_tag and time_tag): continue
            try:
                dt = datetime.strptime(f"{start_dt.year}-{time_tag.text.strip()}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Seoul"))
            except:
                continue
            if dt < start_dt: break
            if start_dt <= dt <= end_dt:
                yonhap_list.append({
                    "source": "연합뉴스", "datetime": dt, "title": title_tag.text.strip(),
                    "url": f"https://www.yna.co.kr/view/{cid}"
                })
        page += 1

    collected += fetch_articles(yonhap_list, "div.story-news.article")

    # 뉴시스
    page, newsis_list = 1, []
    while True:
        url = f"https://www.newsis.com/realnews/?cid=realnews&day=today&page={page}"
        res = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5.0)
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select("ul.articleList2 > li")
        if not items: break
        for item in items:
            title_tag = item.select_one("p.tit > a")
            time_tag = item.select_one("p.time")
            if not (title_tag and time_tag): continue
            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            match = re.search(r"\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}", time_tag.text)
            if not match: continue
            dt = datetime.strptime(match.group(), "%Y.%m.%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Seoul"))
            if dt < start_dt: break
            if start_dt <= dt <= end_dt:
                newsis_list.append({
                    "source": "뉴시스", "datetime": dt, "title": title,
                    "url": "https://www.newsis.com" + href
                })
        page += 1

    collected += fetch_articles(newsis_list, "div.viewer")

    for art in collected:
        matched = [kw for kw in selected_keywords if kw in art['content']]
        st.markdown(f"**[{art['title']}]({art['url']})**")
        st.markdown(f"{art['datetime'].strftime('%Y-%m-%d %H:%M')} | 필터링 키워드: {', '.join(matched)}")
        st.markdown(highlight_keywords(art['content'], matched), unsafe_allow_html=True)
        st.markdown("---")

    return collected

# --- 실행 버튼 ---
if st.button("✅ 선택한 수집기 실행"):
    total_text_block = ""
    if "[단독] 뉴스 수집기" in options:
        dandok_result = fetch_dandok_news()
        for r in dandok_result:
            clean_title = re.sub(r"\[단독\]|\(단독\)|【단독】|^단독\s*[:-]?", "", r['title']).strip()
            total_text_block += f"△{r['media']}/{clean_title}\n- {r['body']}\n\n"

    if "연합뉴스·뉴시스 수집기" in options:
        press_result = fetch_press_news()
        for r in press_result:
            total_text_block += f"△{r['title']}\n- {r['content'][:300]}\n\n"

    if total_text_block:
        st.subheader("📋 복사용 요약 텍스트")
        st.text_area("복사할 내용", total_text_block.strip(), height=400, key="copy_area")
