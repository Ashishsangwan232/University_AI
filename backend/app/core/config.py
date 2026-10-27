from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CampusAI API"
    app_version: str = "0.17.0"
    frontend_origin: str = "http://localhost:5173"
    #: Saved chats live in one SQLite file. Relative paths are resolved from the
    #: backend folder. Any SQLAlchemy URL works if you ever want a server DB.
    database_url: str = "sqlite:///data/campusai.db"
    #: General university facts the bot answers from. Edit it, then restart.
    university_info_file: str = "data/university_info.md"
    #: Search that file by meaning as well as by keyword (hybrid RAG). Runs a
    #: small free embedding model locally with fastembed - no API key, no cost.
    knowledge_embeddings: bool = True
    knowledge_embedding_model: str = "BAAI/bge-small-en-v1.5"
    #: Where the model is downloaded on first run (~67 MB, git-ignored).
    knowledge_embedding_dir: str = "data/rag"
    #: Below this similarity a section only counts if it shares a keyword.
    #: Unrelated questions ("who won the cricket world cup") score about 0.50.
    knowledge_min_similarity: float = 0.52
    # --------------------------------------------------------------- agent
    #: Which model answers by default: "ollama" or "gemini". Both use exactly
    #: the same tools, so this only changes who writes the sentences.
    agent_provider: str = "ollama"
    #: Try the other provider when the chosen one fails or is not configured.
    agent_fallback: bool = True
    #: How many tool-calling rounds a single question may take.
    agent_max_tool_rounds: int = 5

    #: Ollama Cloud. Point this at http://localhost:11434 to use a local
    #: daemon instead - nothing else changes.
    ollama_base_url: str = "https://ollama.com"
    #: "gpt-oss:120b" on Ollama Cloud; "gpt-oss:120b-cloud" through a local
    #: Ollama that is signed in to the cloud.
    ollama_model: str = "gpt-oss:120b"
    #: Never logged, never sent anywhere but the Ollama host above.
    ollama_api_key: str = ""
    ollama_timeout_seconds: int = 120
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    #: OpenAI (Chat Completions). Shows up as a model once the key is set.
    openai_api_key: str = ""
    openai_model: str = "gpt-6-luna"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: int = 120
    #: Read-aloud voice. "edge" = Microsoft Edge's free online neural voice
    #: (no key, no cost; needs internet), with the offline Piper voices as the
    #: backup. "piper" = offline Piper only.
    tts_engine: str = "edge"
    tts_edge_voice: str = "hi-IN-MadhurNeural"  # reads Hindi, Hinglish and English
    tts_edge_timeout_seconds: float = 12.0
    #: Offline Piper voices (the backup). Download: python scripts/download_voices.py
    tts_voice_dir: str = "data/voices"
    tts_voice_hindi: str = "hi_IN-pratham-medium"
    tts_voice_english: str = "en_US-ryan-medium"
    tts_max_chars: int = 1200

    # ------------------------------------------------------- chat memory
    #: Recent turns sent to the model verbatim, so follow-ups resolve.
    chat_history_messages: int = 12
    #: A hard ceiling on that window, so one very long answer cannot crowd out
    #: the rest of the conversation.
    chat_history_character_budget: int = 8000
    #: Once this many turns sit outside the window, they are compressed into
    #: the thread's rolling summary - once, not on every message.
    chat_summary_after_messages: int = 14
    chat_max_conversations: int = 50

    # ------------------------------------------------------------------ UMS
    ums_url: str = "https://ums.lpu.in/lpuums/"
    #: Hostname used to identify the UMS tab. Never rely on tab order.
    ums_host: str = "ums.lpu.in"
    ums_browser_profile: str = "data/ums/playwright-chrome-profile"
    ums_cdp_port: int = 9222
    ums_max_page_text: int = 30000

    #: Comma-separated candidate attendance pages, tried in order when no
    #: in-portal "Attendance" link can be clicked. Each attempt is logged and
    #: recorded in diagnostics; nothing here is assumed to work.
    #: Empty by default: frmStudentCourseWiseAttendanceSummary.aspx is a 404 on
    #: LPU UMS now, and navigating there stranded the browser on an error page.
    #: Attendance is loaded on the dashboard via GetAttendanceDetails() instead.
    ums_attendance_paths: str = ""
    #: Controls clicked to LOAD an attendance panel that has no URL of its own.
    #: LPU UMS renders the table into a modal only after the dashboard tile
    #: #AttPercent calls getAtt(); until then no table exists in the DOM.
    ums_attendance_openers: str = "#AttPercent,[onclick*='getAtt']"
    #: Collapsibles holding the per-course class log in the attendance modal's
    #: second tab: #collapseCSE329, #collapseINT373, and so on.
    ums_attendance_detail_selector: str = "[id^=collapse]"
    #: The page functions UMS's own Attendance tile calls (getAtt() runs both):
    #: read-only requests that fill the summary table and the class-by-class
    #: logs. Calling them directly avoids opening the modal, so a UMS pop-up
    #: covering the tile doesn't matter. Empty = always click the tile instead.
    ums_attendance_summary_loader: str = "GetAttendanceDetails"
    ums_attendance_detail_loader: str = "GetDayWiseAttDetails"

    #: Close the panel we opened once the table has been read.
    ums_close_after_capture: bool = True

    # ------------------------------------------------- announcements & messages
    #: Containers holding announcement cards on the UMS dashboard. From the site
    #: map: #tAC is the announcement centre, #tAM its "mine" tab.
    ums_announcement_containers: str = "#tAC,#tAM"
    #: Controls clicked first to render those containers.
    ums_announcement_openers: str = "#AnnouncementLink"
    #: Page opened when the dashboard panel yields nothing.
    ums_announcement_page: str = "frmHistoryAnnouncemnt.aspx"

    #: Containers holding message cards. #MyMessage is the dashboard panel,
    #: #divMessage and #exampleModalRight the "All Messages" modal.
    ums_message_containers: str = "#MyMessage,#divMessage,#exampleModalRight .modal-body"
    ums_message_openers: str = "#MyMessageLink,[onclick*='getMyAllMessages']"
    ums_message_page: str = "frmStudentsMyMessages.aspx"
    #: The page method UMS's "My Messages Repository" uses: the whole message
    #: history, 20 per page, searchable by subject and text (done by UMS).
    ums_message_store_method: str = "frmStudentsMyMessages.aspx/GetDataforMyMessages"
    #: How many of the latest messages the background reader keeps.
    ums_message_prefetch_rows: int = 60
    #: Most pages (of 20) one search or "last N days" request may read.
    ums_message_max_pages: int = 15
    ums_message_search_ttl_seconds: int = 120

    #: Field selectors inside one card, tried in order. From the DOM inspect:
    #: announcements use .announcement-subject / .announcement-date / .panel-body,
    #: messages use a first .col-sm-12 header and a p.text-small body.
    ums_card_title_selectors: str = ".announcement-subject,.col-sm-12,h1,h2,h3,h4,strong,b"
    ums_card_date_selectors: str = ".announcement-date,.date,[class*=date]"
    ums_card_body_selectors: str = ".panel-body,p.text-small,.message-body"

    #: A card containing more title elements than this is a wrapper around many
    #: items rather than one item, and is skipped. Announcement rows hold 1,
    #: message rows hold 2, the loaded "All Messages" modal holds dozens.
    ums_card_max_title_elements: int = 4

    # ---------------------------------------------------------------- timetable
    #: frmMyCurrentTimeTable.aspx ships empty and fills #timetable by AJAX.
    #: Reports/frmStudentTimeTable.aspx is an SSRS ReportViewer that errors out
    #: on this portal, so it is deliberately not used.
    ums_timetable_page: str = "frmMyCurrentTimeTable.aspx"
    ums_timetable_openers: str = "[onclick*='GetTimeTableData1'],#timetable-tab"
    ums_timetable_container: str = "#timetable"
    ums_timetable_wait_seconds: float = 3.0

    # --------------------------------------------------------------- hostel leave
    #: READ ONLY. CampusAI opens this page with a GET and reads the balances and
    #: authorities. It never fills a field, ticks the acknowledgement, or clicks
    #: Submit - applying for leave stays the student's own action in their own
    #: browser. There is no setting that turns that on.
    ums_leave_page: str = "frmStudentHostelLeaveApplicationTermWise.aspx"
    ums_leave_wait_seconds: float = 2.5

    #: Prefill writes the student's draft into the UMS leave form. OFF by
    #: default. Even when on, it fills the five fields below and stops: the
    #: acknowledgement is never ticked and Submit is never clicked, so the
    #: student still completes the application themselves.
    ums_allow_prefill: bool = False
    #: The ONLY labels whose adjacent field may be written to. The locator
    #: refuses to return a checkbox, button or hidden input for any of them.
    ums_leave_type_label: str = "Leave Type"
    ums_leave_start_label: str = "Start Date & Time of Leave"
    ums_leave_end_label: str = "Leave Ending Date Time"
    ums_leave_place_label: str = "Visit place"
    ums_leave_reason_label: str = "Reason of Leaving"
    #: How the date fields expect a value. If UMS rejects or reformats what is
    #: typed, the read-back will show it and this is the one setting to change.
    ums_leave_datetime_format: str = "%d/%m/%Y %H:%M"

    ums_panel_max_items: int = 60
    ums_panel_max_lines: int = 20
    #: Substrings that indicate a logged-in UMS shell. Two or more must appear
    #: (or an explicit logout control must exist) before Playwright acts.
    ums_dashboard_markers: str = "student dashboard,my academics,attendance,logout,student support,academic"

    ums_auto_navigate: bool = True
    #: How many times the monitor retries automatic capture before waiting for
    #: an explicit Refresh. Prevents an endless click loop in the student's browser.
    ums_auto_capture_attempts: int = 3

    # --------------------------------------------- attendance control discovery
    #: Words that disqualify a clickable control even though it says "attendance"
    #: (event/QR attendance, biometric marking, correction requests, and so on).
    ums_attendance_block_words: str = (
        "event,qr,scan,mark attendance,biometric,face,regulari,correction,request,apply"
    )
    #: Menu labels clicked to reveal a hidden attendance control.
    ums_menu_keywords: str = "academic,my academics,attendance,course,student,menu"
    ums_expand_menus: bool = True
    #: A candidate scoring below this is never clicked.
    ums_min_candidate_score: int = 1
    ums_max_candidate_clicks: int = 5
    ums_max_menu_clicks: int = 3
    #: Remember the control that worked, in data/ums/attendance_target.json.
    #: Only URLs and a CSS path are stored - never cookies, tokens, or content.
    ums_remember_target: bool = True
    ums_monitor_interval_seconds: float = 2.0
    ums_table_wait_seconds: int = 25
    ums_capture_timeout_seconds: int = 90

    # ------------------------------------------------- prefetch & memory cache
    #: Read everything from UMS in the background right after sign-in, so chat
    #: answers come from memory instead of waiting on the portal. Never on disk;
    #: cleared on Disconnect or when UMS shows its login page again.
    ums_prefetch: bool = True
    #: What to read, in this order (most-asked first).
    ums_prefetch_items: str = (
        "attendance,profile,timetable,announcements,messages,leave,attendance_detail"
    )
    #: Re-read an item in the background once it is older than this, while the
    #: worker is idle. Each re-read drives the UMS window, so not too often.
    #: 0 = read once after sign-in and never again.
    ums_refresh_after_seconds: int = 900
    #: Answers use cached data up to this old without waiting; older data is
    #: read from UMS on the spot. Tools always report the data's age.
    ums_cache_max_age_seconds: int = 3600
    #: After a failed prefetch, wait this long before trying that item again.
    ums_prefetch_retry_seconds: int = 120

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def ums_attendance_paths_list(self) -> list[str]:
        return [p.strip() for p in self.ums_attendance_paths.split(",") if p.strip()]

    @property
    def ums_dashboard_markers_list(self) -> list[str]:
        return [m.strip() for m in self.ums_dashboard_markers.split(",") if m.strip()]

    @property
    def ums_attendance_block_words_list(self) -> list[str]:
        return [w.strip().lower() for w in self.ums_attendance_block_words.split(",") if w.strip()]

    @property
    def ums_attendance_openers_list(self) -> list[str]:
        return [o.strip() for o in self.ums_attendance_openers.split(",") if o.strip()]

    @property
    def ums_leave_field_labels(self) -> dict[str, str]:
        """Draft key -> the label whose field it may be written to."""
        return {
            "leave_type": self.ums_leave_type_label,
            "start": self.ums_leave_start_label,
            "end": self.ums_leave_end_label,
            "visit_place": self.ums_leave_place_label,
            "reason": self.ums_leave_reason_label,
        }

    @property
    def ums_announcement_containers_list(self) -> list[str]:
        return [c.strip() for c in self.ums_announcement_containers.split(",") if c.strip()]

    @property
    def ums_announcement_openers_list(self) -> list[str]:
        return [c.strip() for c in self.ums_announcement_openers.split(",") if c.strip()]

    @property
    def ums_message_containers_list(self) -> list[str]:
        return [c.strip() for c in self.ums_message_containers.split(",") if c.strip()]

    @property
    def ums_message_openers_list(self) -> list[str]:
        return [c.strip() for c in self.ums_message_openers.split(",") if c.strip()]

    @property
    def ums_card_title_selectors_list(self) -> list[str]:
        return [c.strip() for c in self.ums_card_title_selectors.split(",") if c.strip()]

    @property
    def ums_card_date_selectors_list(self) -> list[str]:
        return [c.strip() for c in self.ums_card_date_selectors.split(",") if c.strip()]

    @property
    def ums_card_body_selectors_list(self) -> list[str]:
        return [c.strip() for c in self.ums_card_body_selectors.split(",") if c.strip()]

    @property
    def ums_timetable_openers_list(self) -> list[str]:
        return [o.strip() for o in self.ums_timetable_openers.split(",") if o.strip()]

    @property
    def ums_prefetch_items_list(self) -> list[str]:
        return [k.strip().lower() for k in self.ums_prefetch_items.split(",") if k.strip()]

    @property
    def ums_menu_keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.ums_menu_keywords.split(",") if k.strip()]


settings = Settings()
