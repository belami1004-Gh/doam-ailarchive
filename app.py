import os, uuid
from datetime import datetime, date
import streamlit as st
from supabase import create_client
st.set_page_config(page_title='道菴 AI 기록창고', page_icon='📚', layout='wide')
URL=st.secrets.get('SUPABASE_URL',os.getenv('SUPABASE_URL','')); KEY=st.secrets.get('SUPABASE_PUBLISHABLE_KEY',os.getenv('SUPABASE_PUBLISHABLE_KEY',''))
if not URL or not KEY: st.error('Supabase 연결정보를 secrets.toml에 입력하세요.'); st.stop()
sb=create_client(URL,KEY)
st.title('道菴 AI 기록창고'); st.caption('사진과 글을 저장하는 개인 AI 지식 데이터베이스')
if 'session' not in st.session_state: st.session_state.session=None
with st.sidebar:
 st.header('로그인'); email=st.text_input('이메일'); pw=st.text_input('비밀번호',type='password')
 if st.session_state.session is None:
  c1,c2=st.columns(2)
  if c1.button('로그인'):
   try: st.session_state.session=sb.auth.sign_in_with_password({'email':email,'password':pw}).session; st.rerun()
   except Exception as e: st.error(e)
  if c2.button('회원가입'):
   try: sb.auth.sign_up({'email':email,'password':pw}); st.success('가입 요청 완료')
   except Exception as e: st.error(e)
 else:
  st.success('로그인됨')
  if st.button('로그아웃'): sb.auth.sign_out(); st.session_state.session=None; st.rerun()
if st.session_state.session is None: st.info('왼쪽에서 로그인하거나 회원가입하세요.'); st.stop()
sb.auth.set_session(st.session_state.session.access_token, st.session_state.session.refresh_token)
user=st.session_state.session.user
t1,t2=st.tabs(['새 기록','기록 검색'])
with t1:
 with st.form('record',clear_on_submit=True):
  a,b,c=st.columns([1,1,2]); d=a.date_input('날짜',date.today()); tm=b.time_input('시간',datetime.now().time().replace(microsecond=0)); cat=c.selectbox('분류',['여행','주역·철학','강의','지역문화','생활','연구','가족','기타'])
  ㅍ; loc=st.text_input('장소'); photos=st.file_uploader('사진',type=['jpg','jpeg','png','webp','heic'],accept_multiple_files=True); memo=st.text_area('메모'); content=st.text_area('내용',height=180)
  st.markdown('#### AI 영역'); desc=st.text_area('AI 사진설명'); summary=st.text_area('AI 요약'); keys=st.text_input('AI 핵심어',placeholder='제주, 정의향교, 유교문화'); tags=st.text_input('태그',placeholder='제주, 향교, 답사'); ok=st.form_submit_button('저장',type='primary',use_container_width=True)
 if ok:
  if not title.strip(): st.error('제목을 입력하세요.')
  else:
   try:
    row={'user_id':user.id,'record_date':str(d),'record_time':str(tm),'category':cat,'title':title.strip(),'memo':memo,'location':loc,'content':content,'ai_photo_description':desc,'ai_summary':summary,'ai_keywords':[x.strip() for x in keys.split(',') if x.strip()],'tags':[x.strip().lstrip('#') for x in tags.split(',') if x.strip()]}
    rid=sb.table('records').insert(row).execute().data[0]['id']
    for i,p in enumerate(photos or []):
     ext=p.name.rsplit('.',1)[-1].lower() if '.' in p.name else 'bin'; path=f'{user.id}/{rid}/{uuid.uuid4().hex}.{ext}'
     sb.storage.from_('record-photos').upload(path,p.getvalue(),{'content-type':p.type or 'application/octet-stream'})
     sb.table('record_photos').insert({'record_id':rid,'user_id':user.id,'storage_path':path,'original_filename':p.name,'mime_type':p.type,'sort_order':i}).execute()
    st.success(f'저장되었습니다. 기록번호 {rid}')
   except Exception as e: st.error(f'저장 오류: {e}')
with t2:
 q=st.text_input('검색어',placeholder='제목·내용·장소·분류에서 검색')
 try:
  rows=sb.table('records').select('*').order('record_date',desc=True).limit(100).execute().data
  if q.strip():
   s=q.lower(); rows=[r for r in rows if s in ' '.join(str(v or '') for v in r.values()).lower()]
  st.write(f'기록 {len(rows)}건')
  for r in rows:
   with st.expander(f"{r['record_date']} · {r.get('category') or ''} · {r['title']}"):
    st.write('**장소:**',r.get('location') or '-'); st.write('**메모:**',r.get('memo') or '-'); st.write('**내용:**',r.get('content') or '-'); st.write('**AI 요약:**',r.get('ai_summary') or '-'); st.write('**핵심어:**',', '.join(r.get('ai_keywords') or [])); st.write('**태그:**',' '.join('#'+x for x in (r.get('tags') or [])))
    ps=sb.table('record_photos').select('storage_path,original_filename').eq('record_id',r['id']).order('sort_order').execute().data
    for p in ps:
     try:
      x=sb.storage.from_('record-photos').create_signed_url(p['storage_path'],3600); u=x.get('signedURL') or x.get('signedUrl')
      if u: st.image(u,caption=p.get('original_filename'),width=400)
     except: pass
 except Exception as e: st.error(f'조회 오류: {e}')
