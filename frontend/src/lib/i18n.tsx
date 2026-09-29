import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "mk" | "en";

const dict = {
  brand: { mk: "FinkiBOT", en: "FinkiBOT" },
  tagline: { mk: "Асистент за студенти на ФИНКИ", en: "Assistant for FINKI students" },
  nav_chat: { mk: "Разговор", en: "Chat" },
  nav_search: { mk: "Пребарување", en: "Search" },
  nav_quiz: { mk: "Квиз", en: "Quiz" },
  nav_subscribe: { mk: "Известувања", en: "Notifications" },
  nav_insights: { mk: "Увид во податоците", en: "Insights" },
  nav_mcp: { mk: "MCP Алатки", en: "MCP Tools" },
  profile: { mk: "Профил", en: "Profile" },
  guest: { mk: "Гостин", en: "Guest" },
  no_login: { mk: "Без најава", en: "No sign-in needed" },
  settings: { mk: "Поставки", en: "Settings" },
  theme: { mk: "Тема", en: "Theme" },
  light: { mk: "Светла", en: "Light" },
  dark: { mk: "Темна", en: "Dark" },
  system: { mk: "Систем", en: "System" },
  language: { mk: "Јазик", en: "Language" },
  history: { mk: "Историја на разговори", en: "Chat history" },
  new_chat: { mk: "Нов разговор", en: "New chat" },
  no_history: { mk: "Сè уште нема разговори", en: "No conversations yet" },
  delete_chat: { mk: "Избриши разговор", en: "Delete chat" },
  delete_all_chats: { mk: "Избриши ја целата историја", en: "Delete all chats" },
  confirm_delete_all_chats: {
    mk: "Дали сигурно сакаш да ги избришеш сите разговори?",
    en: "Are you sure you want to delete all conversations?",
  },
  chat_placeholder: { mk: "Прашај нешто за ФИНКИ…", en: "Ask something about FINKI…" },
  send: { mk: "Испрати", en: "Send" },
  thinking: { mk: "Размислувам…", en: "Thinking…" },
  answered_by: { mk: "Одговори", en: "Answered by" },
  chat_empty: {
    mk: "Постави прашање за соопштенија, предмети, професори или распоред.",
    en: "Ask about announcements, courses, professors or schedules.",
  },
  search_placeholder: { mk: "Пребарај содржина…", en: "Search content…" },
  submit_search: { mk: "Пребарај", en: "Search" },
  no_results: { mk: "Нема резултати", en: "No results" },
  filter_by_type: { mk: "Филтрирај по тип", en: "Filter by type" },
  filter_by_source: { mk: "Филтрирај по извор", en: "Filter by source" },
  date_from: { mk: "Од датум", en: "From date" },
  date_to: { mk: "До датум", en: "To date" },
  clear_date: { mk: "Исчисти датум", en: "Clear date" },
  material_description: { mk: "Снимени предавања за", en: "Recorded lectures for" },
  type_announcement: { mk: "Соопштение", en: "Announcement" },
  type_course: { mk: "Предмет", en: "Course" },
  type_professor: { mk: "Професор", en: "Professor" },
  type_staff: { mk: "Кадар", en: "Staff" },
  type_material: { mk: "Материјал", en: "Material" },
  type_schedule: { mk: "Распоред", en: "Schedule" },
  type_thesis: { mk: "Дипломска/магистерска", en: "Thesis" },
  type_document: { mk: "Документ", en: "Document" },
  type_page: { mk: "Информативна страница", en: "Info page" },
  type_consultation: { mk: "Консултации", en: "Consultations" },
  loading: { mk: "Се вчитува…", en: "Loading…" },
  error: { mk: "Грешка", en: "Error" },
  source_ref: { mk: "Извор", en: "Source" },
  back: { mk: "← Назад", en: "← Back" },
  professors: { mk: "Професори", en: "Professors" },
  assistants: { mk: "Асистенти", en: "Assistants" },
  tags: { mk: "Тагови", en: "Tags" },
  quiz_upload: { mk: "Прикачи материјал (PDF / PPTX)", en: "Upload material (PDF / PPTX)" },
  num_questions: { mk: "Број на прашања", en: "Number of questions" },
  generate: { mk: "Генерирај квиз", en: "Generate quiz" },
  sources_label: { mk: "Извори", en: "Sources" },
  check_answers: { mk: "Провери одговори", en: "Check answers" },
  reset: { mk: "Ресетирај", en: "Reset" },
  email: { mk: "Е-пошта", en: "Email" },
  keywords: { mk: "Клучни зборови", en: "Keywords" },
  course_codes: { mk: "Кодови на предмети", en: "Course codes" },
  select_course_codes: { mk: "Избери или пребарај предмет…", en: "Select or search a course…" },
  no_courses_found: { mk: "Нема пронајдени предмети", en: "No courses found" },
  add: { mk: "Додај", en: "Add" },
  subscribe: { mk: "Претплати се", en: "Subscribe" },
  subscribe_ok: {
    mk: "Испративме е-порака за потврда. Провери го сандачето.",
    en: "We sent a confirmation email. Please check your inbox.",
  },
  insights_docs: { mk: "Документи по извор и тип", en: "Documents by source and type" },
  insights_months: { mk: "Соопштенија по месец", en: "Announcements by month" },
  insights_tags: { mk: "Најчести тагови на предмети", en: "Most common course tags" },
  insights_sem: { mk: "Предмети по семестар", en: "Courses by semester" },
  run: { mk: "Изврши", en: "Run" },
  results_count: { mk: "Резултати", en: "Results" },
  mcp_intro: {
    mk: "Овие MCP алатки ги изложуваат индексираните податоци од FINKI како стандардизирани, повикливи алатки. Тука можеш да ги пробаш директно.",
    en: "These MCP Tools expose FINKI's indexed data as standardized, callable tools. You can try them here.",
  },
  login: { mk: "Најава", en: "Log in" },
  register: { mk: "Регистрација", en: "Sign up" },
  logout: { mk: "Одјава", en: "Log out" },
  password: { mk: "Лозинка", en: "Password" },
  no_account_yet: { mk: "Немаш сметка?", en: "No account yet?" },
  continue_as_guest: { mk: "Продолжи како гостин", en: "Continue as guest" },
  have_account: { mk: "Веќе имаш сметка?", en: "Already have an account?" },
  new_password: { mk: "Нова лозинка", en: "New password" },
  reset_password: { mk: "Ресетирај лозинка", en: "Reset password" },
  reset_password_ok: {
    mk: "Лозинката е поставена. Сега можеш да се најавиш.",
    en: "Password updated. You can now log in.",
  },
  admin: { mk: "Администрација", en: "Admin" },
  admin_users: { mk: "Корисници", en: "Users" },
  admin_settings: { mk: "Поставки", en: "Settings" },
  admin_only: { mk: "Само за администратори.", en: "Admins only." },
  promote: { mk: "Направи админ", en: "Make admin" },
  demote: { mk: "Одземи админ", en: "Remove admin" },
  activate: { mk: "Активирај", en: "Activate" },
  deactivate: { mk: "Деактивирај", en: "Deactivate" },
  delete: { mk: "Избриши", en: "Delete" },
  confirm_delete: {
    mk: "Дали сигурно сакаш да ја избришеш оваа сметка?",
    en: "Are you sure you want to delete this account?",
  },
  send_reset_link: { mk: "Испрати линк за ресетирање", en: "Send reset link" },
  reset_link_sent: { mk: "Линкот е испратен.", en: "Reset link sent." },
  save: { mk: "Зачувај", en: "Save" },
  saved: { mk: "Зачувано.", en: "Saved." },
  admin_badge: { mk: "Админ", en: "Admin" },
  inactive_badge: { mk: "Неактивна", en: "Inactive" },
  unlimited: { mk: "неограничено", en: "unlimited" },
  reindex_title: { mk: "Ре-индексирање", en: "Reindexing" },
  reindex_hint: {
    mk: "Ги активира скреперите, ги внесува новите документи во базата и го освежува пакуваниот seed (backend/seed/documents.json.gz) за да добијат нови инсталации свежа содржина без сопствено скрепирање. Комитувај го seed-от за да се сподели.",
    en: "Runs the scrapers, ingests new documents into the database, and refreshes the bundled seed (backend/seed/documents.json.gz) so fresh installs get current content without scraping themselves. Commit the seed to share it.",
  },
  reindex_full: { mk: "Целосно", en: "Full" },
  reindex_frequent: { mk: "Брзо (соопштенија)", en: "Frequent (announcements)" },
  reindex_slow: { mk: "Бавно (курсеви, професори)", en: "Slow (courses, professors)" },
  reindex_running: { mk: "Се извршува…", en: "Running…" },
  reindex_sources: { mk: "извори", en: "sources" },
  reindex_elapsed: { mk: "поминато", en: "elapsed" },
  reindex_done_in: { mk: "Готово за", en: "Done in" },
  reindex_no_changes: {
    mk: "Нема нови или изменети документи — сè е веќе актуелно.",
    en: "No new or changed documents — everything is already up to date.",
  },
  reindex_seed_refreshed: {
    mk: "Пакуваниот seed е освежен",
    en: "Bundled seed refreshed",
  },
  reindex_documents: { mk: "документи", en: "documents" },
  reindex_new: { mk: "нови", en: "new" },
  reindex_updated: { mk: "изменети", en: "updated" },
  reindex_seen: { mk: "видени", en: "seen" },
  reindex_failed: { mk: "неуспешни", en: "failed" },
  reindex_incremental: {
    mk: "Само нови документи (побрзо — ги прескокнува веќе зачуваните страници, не забележува измени на нив)",
    en: "New documents only (faster — skips pages already stored, won't notice edits to them)",
  },
  reindex_incremental_tag: { mk: "само нови", en: "new only" },
} as const;

export type TKey = keyof typeof dict;

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (k: TKey) => string }>({
  lang: "mk",
  setLang: () => {},
  t: (k) => dict[k].mk,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("mk");

  useEffect(() => {
    const saved = localStorage.getItem("finkibot-lang");
    if (saved === "en" || saved === "mk") setLangState(saved);
  }, []);

  const setLang = (l: Lang) => {
    setLangState(l);
    localStorage.setItem("finkibot-lang", l);
  };

  const t = (k: TKey) => dict[k][lang];

  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export function useI18n() {
  return useContext(Ctx);
}
