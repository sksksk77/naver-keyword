import streamlit as st
import pandas as pd
import requests
import time
import hmac
import hashlib
import base64
import json
from datetime import datetime
from typing import Optional, Dict, List
import io
import urllib3

# SSL 경고 제거
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 설정
BASE_URL = 'https://api.searchad.naver.com'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# 속도 모드 설정 (tkinter 버전과 동일)
SPEED_MODES = {
    0: {
        'name': '🐢 초안전모드',
        'calls_per_second': 1.5,
        'timeout': 30,
        'retry_count': 2,
        'wait_between_retries': [5, 15]
    },
    1: {
        'name': '🐌 안전모드',
        'calls_per_second': 2.5,
        'timeout': 25,
        'retry_count': 3,
        'wait_between_retries': [5, 10, 20]
    },
    2: {
        'name': '⚖️ 균형모드',
        'calls_per_second': 4.0,
        'timeout': 20,
        'retry_count': 3,
        'wait_between_retries': [3, 8, 15]
    },
    3: {
        'name': '🚗 고속모드',
        'calls_per_second': 6.0,
        'timeout': 15,
        'retry_count': 2,
        'wait_between_retries': [2, 8]
    },
    4: {
        'name': '🚀 초고속모드',
        'calls_per_second': 8.0,
        'timeout': 12,
        'retry_count': 2,
        'wait_between_retries': [2, 5]
    }
}

class NaverKeywordAPI:
    def __init__(self, customer_id: str, access_key: str, secret_key: str):
        self.customer_id = customer_id
        self.access_key = access_key
        self.secret_key = secret_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        })
        
    def generate_signature(self, method: str, uri: str, timestamp: str) -> str:
        """시그니처 생성"""
        message = f"{timestamp}.{method}.{uri}"
        hashed = hmac.new(self.secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
        return base64.b64encode(hashed.digest()).decode('utf-8')
    
    def clean_keyword(self, keyword: str) -> str:
        """키워드 정제 (tkinter 버전과 동일)"""
        if not keyword:
            return ""
        
        # 기본 정제
        cleaned = keyword.strip()
        
        # 연속 공백 제거
        while '  ' in cleaned:
            cleaned = cleaned.replace('  ', ' ')
        
        # 허용 문자만 남기기 (한글, 영문, 숫자, 공백, 기본 특수문자)
        allowed_chars = ''
        for char in cleaned:
            if char.isalnum() or char in 'ㄱ-ㅎㅏ-ㅣ가-힣 .-_':
                allowed_chars += char
        
        # 길이 제한
        result = allowed_chars.strip()
        if len(result) > 50:
            result = result[:50].strip()
        
        return result
    
    def fetch_keyword_data(self, keyword: str, mode_config: dict) -> Optional[Dict]:
        """키워드 데이터 조회 (간소화된 로그)"""
        uri = '/keywordstool'
        
        # 키워드 정제
        cleaned_keyword = self.clean_keyword(keyword)
        if not cleaned_keyword:
            return None
        
        # 재시도 로직
        for attempt in range(mode_config['retry_count']):
            try:
                if attempt > 0:
                    wait_time = mode_config['wait_between_retries'][min(attempt-1, len(mode_config['wait_between_retries'])-1)]
                    time.sleep(wait_time)
                
                # 요청 간격 제어
                time.sleep(1.0 / mode_config['calls_per_second'])
                
                timestamp = str(int(time.time() * 1000))
                signature = self.generate_signature('GET', uri, timestamp)
                
                headers = {
                    'Content-Type': 'application/json; charset=UTF-8',
                    'X-Timestamp': timestamp,
                    'X-API-KEY': self.access_key,
                    'X-Customer': self.customer_id,
                    'X-Signature': signature,
                    'User-Agent': USER_AGENT,
                    'Accept': 'application/json'
                }
                
                params = {
                    'hintKeywords': cleaned_keyword,
                    'showDetail': '1'
                }
                
                response = self.session.get(
                    BASE_URL + uri,
                    headers=headers,
                    params=params,
                    timeout=mode_config['timeout'],
                    verify=True
                )
                
                if response.status_code == 200:
                    try:
                        json_data = response.json()
                        data = json_data.get("keywordList", [])
                        
                        if data and len(data) > 0:
                            first_item = data[0]
                            if isinstance(first_item, dict) and first_item.get('relKeyword'):
                                return first_item
                        
                        return None
                        
                    except json.JSONDecodeError:
                        continue
                        
                elif response.status_code == 403:
                    wait_time = mode_config['wait_between_retries'][min(attempt, len(mode_config['wait_between_retries'])-1)]
                    time.sleep(wait_time)
                    continue
                    
                elif response.status_code == 429:
                    wait_time = mode_config['wait_between_retries'][min(attempt, len(mode_config['wait_between_retries'])-1)]
                    time.sleep(wait_time)
                    continue
                    
                elif response.status_code == 401:
                    return None
                    
                else:
                    continue
                    
            except requests.exceptions.Timeout:
                continue
                
            except Exception as e:
                continue
        
        # 모든 재시도 실패
        return None
    
    def fetch_bid_data(self, keyword: str, mode_config: dict) -> Dict:
        """입찰가 데이터 조회 (간소화된 로그)"""
        uri = '/estimate/average-position-bid/keyword'
        
        def fetch_device_bid(device: str) -> Dict:
            # 요청 간격 제어
            time.sleep(1.0 / mode_config['calls_per_second'])
            
            timestamp = str(int(time.time() * 1000))
            signature = self.generate_signature('POST', uri, timestamp)
            
            headers = {
                'Content-Type': 'application/json; charset=UTF-8',
                'X-Timestamp': timestamp,
                'X-API-KEY': self.access_key,
                'X-Customer': self.customer_id,
                'X-Signature': signature,
                'User-Agent': USER_AGENT,
                'Accept': 'application/json'
            }
            
            clean_kw = self.clean_keyword(keyword)
            if not clean_kw:
                return {f"{device} {pos}위": None for pos in [1, 2, 3, 4, 5]}
            
            items = [{'key': clean_kw, 'position': pos} for pos in [1, 2, 3, 4, 5]]
            body = {'device': device, 'items': items}
            
            try:
                response = self.session.post(
                    BASE_URL + uri,
                    headers=headers,
                    json=body,
                    timeout=mode_config['timeout'],
                    verify=True
                )
                
                if response.status_code == 200:
                    json_data = response.json()
                    estimates = json_data.get('estimate', [])
                    result = {}
                    for item in estimates:
                        pos = item.get('position')
                        bid = item.get('bid')
                        result[f"{device} {pos}위"] = bid
                    return result
                    
            except Exception as e:
                pass
            
            return {f"{device} {pos}위": None for pos in [1, 2, 3, 4, 5]}
        
        bid_results = {}
        bid_results.update(fetch_device_bid('PC'))
        bid_results.update(fetch_device_bid('MOBILE'))
        
        return bid_results

def safe_get_number(value, default=0):
    """안전한 숫자 변환 (tkinter 버전과 동일)"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    
    try:
        if isinstance(value, str):
            if '<' in value:
                value = value.split('<')[-1].strip()
            elif '>' in value:
                value = value.split('>')[-1].strip()
            
            clean_value = ''.join(c for c in value if c.isdigit() or c == '.')
            return int(float(clean_value)) if clean_value else default
    except:
        pass
    
    return default

def safe_format_number(value):
    """안전한 숫자 포맷팅"""
    num = safe_get_number(value, 0)
    return f"{num:,}"

def safe_format_percentage(value):
    """안전한 퍼센티지 포맷팅"""
    if value is None:
        return "0.00%"
    if isinstance(value, (int, float)):
        return f"{round(value * 100, 2):.2f}%"
    return "0.00%"

def safe_format_bid(bid):
    """입찰가 포맷팅 (tkinter 버전과 동일)"""
    if bid is None or bid == "" or bid == 0:
        return "-"
    try:
        if isinstance(bid, (int, float)):
            return f"{int(bid):,}" if bid > 0 else "-"
        bid_str = str(bid).replace(',', '').replace(' ', '')
        if bid_str.replace('.', '', 1).replace('-', '', 1).isdigit():
            return f"{int(float(bid_str)):,}"
        return "-"
    except:
        return "-"

def process_single_keyword(keyword: str, api: NaverKeywordAPI, mode_config: dict, idx: int, total: int) -> Optional[Dict]:
    """단일 키워드 처리 (간소화된 로그)"""
    try:
        # 키워드 데이터 조회
        kw_item = api.fetch_keyword_data(keyword, mode_config)
        
        if not kw_item:
            return None
        
        # 입찰가 데이터 조회
        bid_info_dict = api.fetch_bid_data(keyword, mode_config)
        
        # 데이터 처리
        pc_cnt = safe_get_number(kw_item.get("monthlyPcQcCnt"))
        mob_cnt = safe_get_number(kw_item.get("monthlyMobileQcCnt"))
        total_cnt = pc_cnt + mob_cnt
        
        row = {
            "키워드": str(keyword),
            "PC 검색량": safe_format_number(pc_cnt),
            "모바일 검색량": safe_format_number(mob_cnt),
            "총 검색량": safe_format_number(total_cnt),
            "PC 클릭률": safe_format_percentage(kw_item.get('monthlyAvePcCtr')),
            "모바일 클릭률": safe_format_percentage(kw_item.get('monthlyAveMobileCtr')),
            "경쟁도": str(kw_item.get("compIdx", "-"))
        }
        
        # 입찰가 데이터 추가
        for device in ['PC', 'MOBILE']:
            for pos in [1, 2, 3, 4, 5]:
                column_name = f"{device} {pos}위"
                bid_value = bid_info_dict.get(column_name, None)
                row[column_name] = safe_format_bid(bid_value)
        
        return row
        
    except Exception as e:
        return None

def search_keywords(keywords: List[str], api: NaverKeywordAPI, speed_mode: int):
    """키워드 검색 메인 함수"""
    mode_config = SPEED_MODES[speed_mode]
    total_keywords = len(keywords)
    
    results = []
    failed_keywords = []
    
    # 진행률 표시
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, keyword in enumerate(keywords):
        # 진행률 업데이트
        progress = (idx + 1) / total_keywords
        progress_bar.progress(progress)
        status_text.text(f"진행률: {(idx + 1)}/{total_keywords} ({progress*100:.1f}%) - 현재: '{keyword}'")
        
        # 키워드 처리
        result = process_single_keyword(keyword, api, mode_config, idx, total_keywords)
        
        if result:
            results.append(result)
        else:
            failed_keywords.append(keyword)
    
    # 완료
    progress_bar.progress(1.0)
    status_text.text(f"완료: {len(results)}개 성공, {len(failed_keywords)}개 실패")
    
    return results, failed_keywords

def main():
    st.set_page_config(
        page_title="더장사 키워드 네비게이션 수업용",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔍 더장사 키워드 네비게이션 수업용 v2.0")
    st.markdown("---")
    
    # 사이드바 - API 설정
    with st.sidebar:
        st.header("🔧 API 설정")
        
        customer_id = st.text_input(
            "Customer ID",
            type="password",
            help="네이버 API Customer ID를 입력하세요"
        )
        
        access_key = st.text_input(
            "Access Key",
            type="password",
            help="네이버 API Access Key를 입력하세요"
        )
        
        secret_key = st.text_input(
            "Secret Key",
            type="password",
            help="네이버 API Secret Key를 입력하세요"
        )
        
        st.markdown("---")
        
        # 속도 설정
        st.header("🎛️ 속도 설정")
        speed_mode = st.selectbox(
            "조회 속도",
            options=list(SPEED_MODES.keys()),
            index=1,  # 기본값: 안전모드
            format_func=lambda x: SPEED_MODES[x]['name']
        )
        
        if speed_mode >= 3:
            st.warning("⚠️ 고속 모드는 403 오류 위험이 있습니다! 안전모드 권장!")
        
        st.markdown("---")
        st.markdown("### 📋 특징")
        st.markdown("""
        - ✅ tkinter 버전 로직 적용
        - 🔄 강화된 재시도 메커니즘
        - 🛡️ 403 오류 방지 최적화
        - 📊 실시간 진행률 표시
        - 💾 완전한 데이터 수집
        """)
    
    # 메인 영역
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📝 키워드 입력")
        keyword_input = st.text_area(
            "키워드를 한 줄에 하나씩 입력하세요",
            height=300,
            placeholder="예시:\n키워드1\n키워드2\n키워드3"
        )
        
        # 키워드 개수 표시
        if keyword_input.strip():
            keywords = [line.strip() for line in keyword_input.strip().split('\n') if line.strip()]
            # 중복 제거
            seen = set()
            keywords_unique = [x for x in keywords if x not in seen and not seen.add(x)]
            st.info(f"📊 입력된 키워드: {len(keywords_unique)}개 (중복 제거됨)")
    
    with col2:
        st.header("🚀 조회 실행")
        
        # API 설정 확인
        if not all([customer_id, access_key, secret_key]):
            st.error("❌ 먼저 사이드바에서 API 설정을 완료해주세요!")
            st.stop()
        
        st.success("✅ API 설정 완료")
        
        if st.button("🔍 키워드 조회 시작", type="primary", use_container_width=True):
            if not keyword_input.strip():
                st.error("❌ 키워드를 입력해주세요!")
            else:
                keywords_raw = [line.strip() for line in keyword_input.strip().split('\n') if line.strip()]
                
                # 키워드 전처리 및 중복 제거
                seen = set()
                keywords_processed = []
                
                for kw in keywords_raw:
                    if kw not in seen:
                        seen.add(kw)
                        keywords_processed.append(kw)
                
                if not keywords_processed:
                    st.error("❌ 유효한 키워드가 없습니다!")
                else:
                    # API 객체 생성
                    api = NaverKeywordAPI(customer_id, access_key, secret_key)
                    
                    # 키워드 처리
                    mode_info = SPEED_MODES[speed_mode]
                    with st.spinner(f"{mode_info['name']}로 키워드 조회 중..."):
                        results, failed_keywords = search_keywords(keywords_processed, api, speed_mode)
                    
                    # 결과 저장
                    st.session_state.results = results
                    st.session_state.failed_keywords = failed_keywords
                    st.session_state.last_search_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 결과 표시
    if 'results' in st.session_state and st.session_state.results:
        st.markdown("---")
        st.header("📊 조회 결과")
        
        # 결과 요약 정보
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 키워드", len(st.session_state.results))
        
        with col2:
            total_attempted = len(st.session_state.results) + len(st.session_state.get('failed_keywords', []))
            success_rate = (len(st.session_state.results) / total_attempted * 100) if total_attempted > 0 else 0
            st.metric("성공률", f"{success_rate:.1f}%")
        
        with col3:
            st.metric("실패 키워드", len(st.session_state.get('failed_keywords', [])))
        
        with col4:
            st.metric("조회 시간", st.session_state.get('last_search_time', '-'))
        
        # 결과 테이블
        df = pd.DataFrame(st.session_state.results)
        
        # 컬럼 순서 정렬
        ordered_cols = [
            "키워드", "PC 검색량", "모바일 검색량", "총 검색량",
            "PC 클릭률", "모바일 클릭률", "경쟁도",
            "PC 1위", "PC 2위", "PC 3위", "PC 4위", "PC 5위",
            "MOBILE 1위", "MOBILE 2위", "MOBILE 3위", "MOBILE 4위", "MOBILE 5위"
        ]
        
        df_cols = [col for col in ordered_cols if col in df.columns]
        df = df[df_cols]
        
        st.dataframe(df, use_container_width=True, height=400)
        
        # 엑셀 다운로드
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # 엑셀 파일 생성
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='키워드 조회 결과', index=False)
                
                # 실패 키워드도 추가
                if st.session_state.get('failed_keywords'):
                    failed_df = pd.DataFrame({'실패한 키워드': st.session_state.failed_keywords})
                    failed_df.to_excel(writer, sheet_name='실패 키워드', index=False)
            
            excel_data = output.getvalue()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            success_rate_str = f"{success_rate:.0f}percent" if 'success_rate' in locals() else "result"
            filename = f"naver_keywords_{success_rate_str}_{timestamp}.xlsx"
            
            st.download_button(
                label="📂 엑셀 다운로드",
                data=excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        
        # 실패 키워드 표시
        if st.session_state.get('failed_keywords'):
            with st.expander(f"❌ 실패한 키워드 ({len(st.session_state.failed_keywords)}개)"):
                for keyword in st.session_state.failed_keywords:
                    st.text(f"• {keyword}")
    
    # 푸터
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 12px;'>
        🔍 더장사 키워드 네비게이션 수업용 v2.0<br>
        📊 총 17개 컬럼: 검색량 + PC/모바일 1-5위 입찰가 완전 지원
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
