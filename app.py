import base64
import json
import mimetypes
import os
import uuid
from datetime import date, datetime

import streamlit as st
from openai import OpenAI
from supabase import create_client

st.set_page_config(page_title="道菴 AI 기록창고", page_icon="📚", layout="wide")
st.title("道菴 AI 기록창고")
st.caption("사진과 글을 저장하고 AI로 분석하는 개인 지식 데이터베이스")

URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
KEY = st.secrets.get("SUPABASE_PUBLISHABLE_KEY", os.getenv("SUPABASE_PUBLISHABLE_KEY", ""))
AI_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
if not URL or not KEY:
    st.error("Supabase 연결정보가 없습니다. Streamlit Secrets를 확인하세요.")
    st.stop()

sb = create_client(URL, KEY)
if "session" not in st.session_state:
    st.session_state.session = None

with st.sidebar:
    st.header("로그인")
    if st.session_state.session is None:
        email = st.text_input("이메일")
        password = st.text_input("비밀번호", type="password")
        a, b = st.columns(2)
        if a.button("로그인"):
            try:
                st.session_state.session = sb.auth.sign_in_with_password(
                    {"email": email, "password": password}
                ).session
                st.rerun()
            except Exception as exc:
                st.error(f"로그인 오류: {exc}")
        if b.button("회원가입"):
            try:
                sb.auth.sign_up({"email": email, "password": password})
                st.success("가입 요청이 접수되었습니다. 이메일을 확인하세요.")
            except Exception as exc:
                st.error(f"회원가입 오류: {exc}")
    else:
        st.success("로그인됨")
        if st.button("로그아웃"):
            try:
                sb.auth.sign_out()
            except Exception:
                pass
            st.session_state.session = None
            st.rerun()

if st.session_state.session is None:
    st.info("왼쪽에서 로그인하거나 회원가입하세요.")
    st.stop()

try:
    auth_result = sb.auth.set_session(
        st.session_state.session.access_token,
        st.session_state.session.refresh_token,
    )
    st.session_state.session = auth_result.session
    user = auth_result.user
except Exception:
    st.session_state.session = None
    st.warning("로그인이 만료되었습니다. 다시 로그인하세요.")
    st.stop()


def analyze_record(title, category, location, memo, content, photos):
    if not AI_KEY:
        raise RuntimeError("OPENAI_API_KEY가 등록되지 않았습니다.")
    client = OpenAI(api_key=AI_KEY, timeout=35.0, max_retries=1)
    instructions = (
        "당신은 한국어 개인기록 아카이브의 분석가입니다. 제공된 내용과 이미지에 근거하여 "
        "JSON 객체만 반환하세요. 키는 photo_description, summary, keywords 입니다. "
        "photo_description은 이미지가 있을 때만 관찰 가능한 내용을 1~3문장으로 쓰고 "
        "이미지가 없으면 빈 문자열로 작성하세요. summary는 2~3문장, "
        "keywords는 한국어 단어 문자열 배열 최대 6개입니다. "
        "불확실한 지명, 인물, 연대는 단정하지 마세요."
    )
    description = (
        f"제목: {title}\n분류: {category}\n장소: {location}\n"
        f"메모: {memo}\n본문: {content}"
    )
    parts = [{"type": "input_text", "text": description}]
    supported = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    for photo in (photos or [])[:2]:
        mime = photo.type or mimetypes.guess_type(photo.name)[0] or ""
        if mime not in supported:
            continue
        encoded = base64.b64encode(photo.getvalue()).decode("ascii")
        parts.append({"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"})
    response = client.responses.create(
        model="gpt-4.1-mini",
        instructions=instructions,
        input=[{"role": "user", "content": parts}],
        text={"format": {"type": "json_object"}},
        max_output_tokens=500,
    )
    result = json.loads(response.output_text)
    keywords = result.get("keywords", [])
    if not isinstance(keywords, list):
        keywords = []
    return (
        str(result.get("photo_description") or ""),
        str(result.get("summary") or ""),
        [str(x).strip() for x in keywords[:6] if str(x).strip()],
    )


def photo_link(path):
    result = sb.storage.from_("record-photos").create_signed_url(path, 3600)
    return result.get("signedURL") or result.get("signedUrl") or result.get("signed_url")


t1, t2 = st.tabs(["새 기록", "기록 검색"])
with t1:
    with st.form("record", clear_on_submit=True):
        a, b, c = st.columns([1, 1, 2])
        record_date = a.date_input("날짜", date.today())
        record_time = b.time_input("시간", datetime.now().time().replace(microsecond=0))
        category = c.selectbox("분류", ["여행", "주역·철학", "강의", "지역문화", "생활", "연구", "가족", "기타"])
        title = st.text_input("제목 *", help="한글 마지막 글자가 빠지면 저장 전에 스페이스바를 눌러 조합을 확정하세요.")
        location = st.text_input("장소")
        photos = st.file_uploader("사진", type=["jpg", "jpeg", "png", "webp", "heic"], accept_multiple_files=True)
        memo = st.text_area("메모")
        content = st.text_area("내용", height=180)
        st.markdown("#### AI 분석")
        use_ai = st.checkbox("저장할 때 AI로 사진 설명·요약·핵심어 자동 생성", value=True)
        manual_description = st.text_area("사진 설명 (AI 미사용 시 직접 입력)")
        manual_summary = st.text_area("요약 (AI 미사용 시 직접 입력)")
        manual_keywords = st.text_input("핵심어 (쉼표로 구분)")
        tags = st.text_input("태그 (쉼표로 구분)")
        submitted = st.form_submit_button("저장", type="primary", use_container_width=True)

    if submitted:
        if not title.strip():
            st.error("제목을 입력하세요.")
        else:
            description = manual_description
            summary = manual_summary
            keywords = [x.strip() for x in manual_keywords.split(",") if x.strip()]
            if use_ai:
                try:
                    with st.spinner("AI가 기록을 분석하고 있습니다..."):
                        description, summary, keywords = analyze_record(
                            title.strip(), category, location, memo, content, photos
                        )
                    st.success("AI 분석 완료")
                except Exception as exc:
                    st.warning(f"AI 분석을 수행하지 못했습니다. 원본 기록은 저장합니다. 원인: {exc}")
            try:
                row = {
                    "user_id": user.id,
                    "record_date": str(record_date),
                    "record_time": str(record_time),
                    "category": category,
                    "title": title.strip(),
                    "memo": memo,
                    "location": location,
                    "content": content,
                    "ai_photo_description": description,
                    "ai_summary": summary,
                    "ai_keywords": keywords,
                    "tags": [x.strip().lstrip("#") for x in tags.split(",") if x.strip()],
                }
                saved = sb.table("records").insert(row).execute().data
                record_id = saved[0]["id"]
                failed = []
                for i, photo in enumerate(photos or []):
                    try:
                        ext = photo.name.rsplit(".", 1)[-1].lower() if "." in photo.name else "bin"
                        path = f"{user.id}/{record_id}/{uuid.uuid4().hex}.{ext}"
                        sb.storage.from_("record-photos").upload(
                            path, photo.getvalue(), {"content-type": photo.type or "application/octet-stream"}
                        )
                        sb.table("record_photos").insert({
                            "record_id": record_id,
                            "user_id": user.id,
                            "storage_path": path,
                            "original_filename": photo.name,
                            "mime_type": photo.type,
                            "sort_order": i,
                        }).execute()
                    except Exception as exc:
                        failed.append(f"{photo.name}: {exc}")
                st.success(f"저장되었습니다. 기록번호 {record_id}")
                if failed:
                    st.warning("일부 사진 저장 실패: " + "; ".join(failed))
            except Exception as exc:
                st.error(f"저장 오류: {exc}")

with t2:
    query = st.text_input("검색어", placeholder="제목·내용·장소·분류에서 검색")
    try:
        rows = sb.table("records").select("*").order("record_date", desc=True).limit(100).execute().data
        if query.strip():
            term = query.casefold()
            rows = [r for r in rows if term in " ".join(str(v or "") for v in r.values()).casefold()]
        st.write(f"기록 {len(rows)}건 (최근 최대 100건 조회)")
        for r in rows:
            with st.expander(f"{r['record_date']} · {r.get('category') or ''} · {r['title']}"):
                st.write("**장소:**", r.get("location") or "-")
                st.write("**메모:**", r.get("memo") or "-")
                st.write("**내용:**", r.get("content") or "-")
                st.write("**AI 사진설명:**", r.get("ai_photo_description") or "-")
                st.write("**AI 요약:**", r.get("ai_summary") or "-")
                st.write("**핵심어:**", ", ".join(r.get("ai_keywords") or []))
                st.write("**태그:**", " ".join("#" + x for x in (r.get("tags") or [])))
                pictures = sb.table("record_photos").select("storage_path,original_filename").eq("record_id", r["id"]).order("sort_order").execute().data
                for picture in pictures:
                    try:
                        url = photo_link(picture["storage_path"])
                        if url:
                            st.image(url, caption=picture.get("original_filename"), width=400)
                    except Exception:
                        st.warning("사진을 표시하지 못했습니다.")
    except Exception as exc:
        st.error(f"조회 오류: {exc}")
