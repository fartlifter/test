import streamlit as st
import requests, httpx, re
from bs4 import BeautifulSoup
from datetime import datetime, date, time as dtime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== 키워드 그룹 =====
keyword_groups = {
    '시경': ['서울경찰청'],
    '본청': ['경찰청'],
    '종혜북': ['종로', '종암', '성북', '고려대', '참여연대', '혜화', '동대문', '중랑',
              '성균관대', '한국외대', '서울시립대', '경희대', '경실련', '서울대병원',
              '노원', '강북', '도봉', '북부지법', '북부지검', '상계백병원', '국가인권위원회'],
    '마포중부': ['마포', '서대문', '서부', '은평', '서부지검', '서부지법', '연세대', '신촌세브란스병원',
               '군인권센터', '중부', '남대문', '용산', '동국대', '숙명여대', '순천향대병원'],
    '영등포관악': ['영등포', '양천', '구로', '강서', '남부지검', '남부지법', '여의도성모병원',
                 '고대구로병원', '관악', '금천', '동작', '방배', '서울대', '중앙대', '숭실대', '보라매병원'],
    '강남광진': ['강남', '서초', '수서', '송파', '강동', '삼성의료원', '현대아산병원', '강남세브란스병원',
               '광진', '성동', '동부지검', '동부지법', '한양대', '건국대', '세종대']
}

# ===== 날짜 및 키워드 선택 UI =====
st.set_page_config(page_title="뉴스 키워드 통합 수집기", layout="wide")
st.title("📰 뉴스 키워드 통합 수집기")

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

selected_groups = st.multiselect("📚 키워드 그룹", list(keyword_groups.keys()), default=['시경', '종혜북'])
selected_keywords = [kw for g in selected_groups for kw in keyword_groups[g]]
use_filter = st.checkbox("📎 키워드 포함 기사만 보기", value=True)

options = st.multiselect("🧭 실행할 수집기 선택", ["[단독] 뉴스 수집기", "연합뉴스·뉴시스 수집기"])
run_btn = st.button("✅ 선택한 수집기 실행")

# ===== 진행 상태 표시 영역 =====
status_area = st.empty()
progress_area = st.empty()

# ===== [단독] 뉴스 수집 =====
def fetch_dandok_news():
    status_area.info("🔍 [단독] 뉴스 수집 중...")
    progress = progress_area.progress(0.0)

    client_id = "R7Q2OeVNhj8wZtNNFBwL"
    client_secret = "49E810CBKY"
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}

    results = []
    seen_links = set()
    idx = 0

    for start_index in range(1, 1001, 100):
        params = {
            "query": "[단독]",
            "sort": "date",
            "display": 100,
            "start": start_index
        }
        res = requests.get("https://openapi.naver.com/v1/search/news.json", headers=headers, params=params)
        if res.status_code != 200: break
        items = res.json().get("items", [])
        if not items: break

        for item in items:
            title = BeautifulSoup(item["title"], "html.parser").get_text()
            link = item.get("link")
            if "[단독]" not in title or not link or "n.news.naver.com" not in link:
                continue
            pub_str = item.get("pubDate")
            pub_dt = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %z")
            if not (start_dt <= pub_dt <= end_dt):
                continue
            html = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            soup = BeautifulSoup(html.text, "html.parser")
            body = soup.find("div", id="newsct_article")
            if not body:
                continue
            text = body.get_text("\n", strip=True)
            matched = [kw for kw in selected_keywords if kw in text] if use_filter else []
            if use_filter and not matched: continue
            results.append({
                "title": title, "link": link, "date": pub_dt.strftime("%Y-%m-%d %H:%M"),
                "content": text, "matched": matched
            })
            idx += 1
            progress.progress(min(idx / 300, 1.0), text=f"[단독] {idx}건 수집됨")

    status_area.success(f"✅ [단독] 기사 {idx}건 수집 완료")
    progress_area.empty()
    return results

# ===== 연합뉴스 · 뉴시스 수집 =====
def fetch_press_news():
    status_area.info("🔍 연합뉴스·뉴시스 기사 수집 중...")
    collected = []
    progress = progress_area.progress(0.0)
    count = 0

    def fetch(url, selector):
        try:
            res = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5.0)
            soup = BeautifulSoup(res.text, "html.parser")
            el = soup.select_one(selector)
            return el.get_text("\n", strip=True) if el else ""
        except:
            return ""

    def parse_articles(article_list, selector):
        nonlocal count
        results = []
        total = len(article_list)
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(fetch, a['url'], selector): a for a in article_list}
            for i, future in enumerate(as_completed(futures)):
                a = futures[future]
                try:
                    content = future.result()
                    if any(kw in content for kw in selected_keywords):
                        a['content'] = content
                        results.append(a)
                        count += 1
                        progress.progress((i + 1) / total, text=f"본문 수집 {i+1}/{total}")
                except:
                    continue
        return results

    # 연합뉴스
    page, yonhap = 1, []
    while True:
        url = f"https://www.yna.co.kr/news/{page}?site=navi_latest_depth01"
        soup = BeautifulSoup(httpx.get(url).text, "html.parser")
        items = soup.select("ul.list01 > li[data-cid]")
        if not items: break
        for item in items:
            title = item.select_one(".title01")
            time_ = item.select_one(".txt-time")
            cid = item.get("data-cid")
            if not title or not time_ or not cid: continue
            dt = datetime.strptime(f"{start_dt.year}-{time_.text.strip()}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Seoul"))
            if dt < start_dt: break
            if dt > end_dt: continue
            yonhap.append({
                "source": "연합뉴스", "datetime": dt, "title": title.text.strip(),
                "url": f"https://www.yna.co.kr/view/{cid}"
            })
        page += 1
    collected += parse_articles(yonhap, "div.story-news.article")

    # 뉴시스
    page, newsis = 1, []
    while True:
        url = f"https://www.newsis.com/realnews/?cid=realnews&day=today&page={page}"
        soup = BeautifulSoup(httpx.get(url).text, "html.parser")
        items = soup.select("ul.articleList2 > li")
        if not items: break
        for item in items:
            title = item.select_one("p.tit > a")
            time_ = item.select_one("p.time")
            if not title or not time_: continue
            match = re.search(r"\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}", time_.text)
            if not match: continue
            dt = datetime.strptime(match.group(), "%Y.%m.%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Seoul"))
            if dt < start_dt: break
            if dt > end_dt: continue
            newsis.append({
                "source": "뉴시스", "datetime": dt, "title": title.text.strip(),
                "url": "https://www.newsis.com" + title.get("href")
            })
        page += 1
    collected += parse_articles(newsis, "div.viewer")

    progress_area.empty()
    status_area.success(f"✅ 연합뉴스·뉴시스 기사 {count}건 수집 완료")
    return collected

# ===== 실행 버튼 클릭 시 =====
if run_btn:
    all_articles = []
    if "[단독] 뉴스 수집기" in options:
        all_articles += fetch_dandok_news()
    if "연합뉴스·뉴시스 수집기" in options:
        all_articles += fetch_press_news()

    if all_articles:
        st.subheader("📋 수집된 기사")
        for a in all_articles:
            st.markdown(f"**[{a['title']}]({a['url']})**")
            if 'datetime' in a:
                st.caption(a['datetime'].strftime("%Y-%m-%d %H:%M"))
            if a.get("matched"):
                st.write(f"**일치 키워드:** {', '.join(a['matched'])}**")
            st.markdown(a['content'][:500].replace("\n", "<br>"), unsafe_allow_html=True)
            st.markdown("---")

        # 요약 텍스트 생성
        summary = ""
        for a in all_articles:
            title = re.sub(r"\[단독\]|\(단독\)|【단독】|^단독\s*[:-]?", "", a['title']).strip()
            summary += f"△{a.get('source', '단독')}/{title}\n- {a['content'][:300].replace('\n', ' ')}\n\n"

        st.subheader("🧾 복사용 텍스트")
        st.text_area("복사하세요", summary.strip(), height=400, key="summary_box")
