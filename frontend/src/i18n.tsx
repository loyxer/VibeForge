// Interface language: Ukrainian or English, switched in the header and
// remembered in this browser. Every visible string lives here, so a new
// piece of UI needs its text added to both dictionaries (TypeScript makes
// sure the Ukrainian one has every key the English one has).

import { createContext, ReactNode, useContext, useEffect, useState } from 'react'

export type Lang = 'uk' | 'en'

const en = {
  'app.tagline': 'Describe a site in plain words — watch it build, live.',
  'app.language': 'Language',
  'app.account': 'Account',
  'app.signOut': 'Sign out',
  'app.mySites': 'My sites',
  'footer.privacy': 'Privacy',
  'footer.terms': 'Terms',
  'footer.unsplash': 'Photos by Unsplash',

  'usage.label': 'Left today',
  'usage.count': '{left} of {limit}',
  'usage.none': 'No generations left today',
  'usage.limitReached': "You've used all {limit} free generations for today — more tomorrow.",

  'chat.newSite': 'New site',
  'chat.newSiteButton': '+ New site',
  'chat.empty': 'Describe the site you want, e.g. “a landing page for a coffee shop with a menu and prices”.',
  'chat.labelNew': 'What site shall we make?',
  'chat.labelEdit': 'What should change?',
  'chat.placeholderNew': 'e.g. a landing page for a coffee shop with a menu',
  'chat.placeholderEdit': 'e.g. make the buttons darker',
  'chat.send': 'Create site',
  'chat.sendEdit': 'Apply changes',
  'chat.sending': 'Building…',
  'chat.style': 'Site style',
  'chat.mascot': 'Spark, the VibeForge helper',

  'progress.starting': 'Spark is getting started…',
  'progress.writing': 'Spark is writing your site… {kb} KB',
  'progress.generating': 'Spark is working…',

  'reply.done': 'Done! What shall we change next?',
  'reply.doneEarlier': 'Done.',
  'reply.restored': 'Done — that version is back.',
  'reply.saved': 'Saved your changes.',
  'reply.error': 'Error: {detail}',

  'error.interrupted': 'The connection was interrupted — please try again.',
  'error.generation': 'Could not build the site',
  'error.restore': 'Could not restore that version.',
  'error.save': 'Could not save',
  'error.generic': 'Something went wrong — please try again.',
  'error.server': 'Server error: {status}',

  'style.auto': 'Auto',
  'style.minimal': 'Minimal',
  'style.bold': 'Bold',
  'style.neon': 'Neon',
  'style.retro': 'Retro',
  'style.elegant': 'Elegant',
  'style.playful': 'Playful',

  'preview.title': 'Preview',
  'preview.published': 'Published',
  'preview.unpublishedChanges': 'Changes not published',
  'preview.empty': 'Your site will appear here',
  'preview.emptyBuilding': 'Your site will appear here as it is written…',
  'preview.building': 'Building…',
  'preview.frame': 'Site preview',
  'preview.frameNext': 'Next version (loading)',
  'preview.frameEdit': 'Editing the text',

  'viewing.label': 'Viewing version {number}',
  'viewing.restore': 'Restore this version',
  'viewing.back': 'Back to latest',
  'editing.hint': 'Click any text on the page to change it. Buttons and menus on the site are paused while you edit.',
  'editing.save': 'Save changes',
  'editing.saving': 'Saving…',
  'editing.cancel': 'Cancel',

  'actions.editText': 'Edit text',
  'actions.editTextHint': 'Change any text yourself — free, no AI',
  'actions.history': 'History',
  'actions.hideHistory': 'Hide history',
  'actions.download': 'Download',
  'actions.publish': 'Publish',
  'actions.publishing': 'Publishing…',
  'actions.liveAt': 'Live at',
  'actions.copy': 'Copy link',
  'actions.copied': 'Copied!',
  'actions.unpublish': 'Unpublish',
  'actions.stale': "Your latest changes aren't live yet.",
  'actions.update': 'Update published site',
  'actions.updating': 'Updating…',

  'history.loading': 'Loading history…',
  'history.first': 'First version',
  'history.current': 'current',
  'history.justNow': 'just now',
  'history.minutes': '{n} min ago',
  'history.hours': '{n} h ago',

  'gallery.title': 'My sites',
  'gallery.close': 'Close',
  'gallery.empty': 'Your sites will show up here once you make one.',
  'gallery.loading': 'Loading…',
  'gallery.open': 'Open',
  'gallery.delete': 'Delete',
  'gallery.confirmDelete': 'Delete “{name}”? This cannot be undone.',
  'gallery.steps.one': '{n} step',
  'gallery.steps.few': '{n} steps',
  'gallery.steps.many': '{n} steps',
  'gallery.steps.other': '{n} steps',
  'gallery.current': 'Open now',
  'account.changePassword': 'Change password',
  'account.newPassword': 'New password',
  'account.repeatPassword': 'Repeat the new password',
  'account.mismatch': "The passwords don't match.",
  'account.passwordChanged': 'Your password has been changed.',
  'account.save': 'Save',
  'account.cancel': 'Cancel',
  'account.deleteTitle': 'Delete account',
  'account.deleteWarning':
    'This deletes your account and all your sites right away, including published ones — their links stop working. This cannot be undone.',
  'account.deleteConfirm': 'Delete everything',
  'account.deleteFailed': 'Could not delete the account — please try again.',
  'gallery.rename': 'Rename',
  'gallery.renameLabel': 'Site name',

  'signin.title': 'Sign in to start building',
  'signin.intro': "Your sites are saved to your account, so they're here next time you come back.",
  'signin.submit': 'Sign in',
  'signin.toSignup': 'Create an account',
  'signin.toForgot': 'Forgot password?',
  'signup.title': 'Create your account',
  'signup.intro': "We'll email you a code to confirm the address.",
  'signup.submit': 'Create account',
  'signup.toSignin': 'I already have an account',
  'confirm.title': 'Check your email',
  'confirm.submit': 'Confirm',
  'confirm.resend': 'Send a new code',
  'forgot.title': 'Reset your password',
  'forgot.intro': "We'll email you a code to set a new one.",
  'forgot.submit': 'Send code',
  'reset.title': 'Set a new password',
  'reset.submit': 'Save and sign in',
  'auth.back': 'Back to sign in',
  'auth.or': 'or',
  'auth.google': 'Continue with Google',
  'auth.email': 'Email',
  'auth.password': 'Password',
  'auth.newPassword': 'Password (at least 8 characters)',
  'auth.resetPassword': 'New password (at least 8 characters)',
  'auth.code': 'Code from the email',
  'auth.notConfirmed': "Your email isn't confirmed yet — we sent a new code to {email}.",
  'auth.alreadyRegistered': 'This email is already registered — sign in instead.',
  'auth.codeSent': 'We sent a code to {email}. It may take a minute.',
  'auth.codeResent': 'New code sent to {email}.',
  'auth.resetSent': 'If {email} has an account, we sent it a code.',
  'auth.invalidCredentials': 'Wrong email or password.',
  'auth.badCode': 'The code is wrong or has expired — ask for a new one.',
  'auth.weakPassword': 'The password is too short — use at least 8 characters.',
  'auth.rateLimit': 'Too many emails in a short time — wait a few minutes and try again.',
  'auth.samePassword': 'The new password must be different from the old one.',
} as const

export type Key = keyof typeof en

const uk: Record<Key, string> = {
  'app.tagline': 'Опиши сайт звичайними словами — і дивись, як він з’являється.',
  'app.language': 'Мова',
  'app.account': 'Акаунт',
  'app.signOut': 'Вийти',
  'app.mySites': 'Мої сайти',
  'footer.privacy': 'Конфіденційність',
  'footer.terms': 'Умови',
  'footer.unsplash': 'Фото з Unsplash',

  'usage.label': 'Залишилось',
  'usage.count': '{left} з {limit}',
  'usage.none': 'На сьогодні все',
  'usage.limitReached': 'Безкоштовні генерації на сьогодні закінчились ({limit} з {limit}) — нові з’являться завтра.',

  'chat.newSite': 'Новий сайт',
  'chat.newSiteButton': '+ Новий сайт',
  'chat.empty': 'Опиши сайт, який хочеш, наприклад: «лендинг для кав’ярні з меню та цінами».',
  'chat.labelNew': 'Який сайт створимо?',
  'chat.labelEdit': 'Що змінити?',
  'chat.placeholderNew': 'наприклад: лендинг для кав’ярні з меню',
  'chat.placeholderEdit': 'наприклад: зроби кнопки темнішими',
  'chat.send': 'Створити сайт',
  'chat.sendEdit': 'Внести зміни',
  'chat.sending': 'Створюю…',
  'chat.style': 'Стиль сайту',
  'chat.mascot': 'Іскра, помічниця VibeForge',

  'progress.starting': 'Іскра береться до роботи…',
  'progress.writing': 'Іскра пише сайт… {kb} КБ',
  'progress.generating': 'Іскра працює…',

  'reply.done': 'Готово! Що змінимо далі?',
  'reply.doneEarlier': 'Готово.',
  'reply.restored': 'Готово — цю версію повернуто.',
  'reply.saved': 'Зміни збережено.',
  'reply.error': 'Помилка: {detail}',

  'error.interrupted': 'З’єднання перервалося — спробуй ще раз.',
  'error.generation': 'Не вдалося створити сайт',
  'error.restore': 'Не вдалося повернути цю версію.',
  'error.save': 'Не вдалося зберегти',
  'error.generic': 'Щось пішло не так — спробуй ще раз.',
  'error.server': 'Помилка сервера: {status}',

  'style.auto': 'Авто',
  'style.minimal': 'Мінімалізм',
  'style.bold': 'Сміливий',
  'style.neon': 'Неон',
  'style.retro': 'Ретро',
  'style.elegant': 'Елегантний',
  'style.playful': 'Грайливий',

  'preview.title': 'Перегляд',
  'preview.published': 'Опубліковано',
  'preview.unpublishedChanges': 'Є неопубліковані зміни',
  'preview.empty': 'Тут з’явиться твій сайт',
  'preview.emptyBuilding': 'Сайт з’являтиметься тут по ходу написання…',
  'preview.building': 'Створюю…',
  'preview.frame': 'Перегляд сайту',
  'preview.frameNext': 'Наступна версія (завантажується)',
  'preview.frameEdit': 'Редагування тексту',

  'viewing.label': 'Ти переглядаєш версію {number}',
  'viewing.restore': 'Повернути цю версію',
  'viewing.back': 'До останньої версії',
  'editing.hint': 'Клацни на будь-який текст на сторінці, щоб змінити його. Кнопки й меню сайту на паузі, поки ти редагуєш.',
  'editing.save': 'Зберегти зміни',
  'editing.saving': 'Зберігаю…',
  'editing.cancel': 'Скасувати',

  'actions.editText': 'Редагувати текст',
  'actions.editTextHint': 'Зміни будь-який текст сам — безкоштовно, без AI',
  'actions.history': 'Історія',
  'actions.hideHistory': 'Сховати історію',
  'actions.download': 'Завантажити',
  'actions.publish': 'Опублікувати',
  'actions.publishing': 'Публікую…',
  'actions.liveAt': 'Сайт онлайн:',
  'actions.copy': 'Скопіювати посилання',
  'actions.copied': 'Скопійовано!',
  'actions.unpublish': 'Зняти з публікації',
  'actions.stale': 'Останні зміни ще не опубліковані.',
  'actions.update': 'Оновити публікацію',
  'actions.updating': 'Оновлюю…',

  'history.loading': 'Завантажую історію…',
  'history.first': 'Перша версія',
  'history.current': 'поточна',
  'history.justNow': 'щойно',
  'history.minutes': '{n} хв тому',
  'history.hours': '{n} год тому',

  'gallery.title': 'Мої сайти',
  'gallery.close': 'Закрити',
  'gallery.empty': 'Тут з’являться твої сайти, щойно ти створиш перший.',
  'gallery.loading': 'Завантажую…',
  'gallery.open': 'Відкрити',
  'gallery.delete': 'Видалити',
  'gallery.confirmDelete': 'Видалити «{name}»? Цю дію не можна скасувати.',
  'gallery.steps.one': '{n} крок',
  'gallery.steps.few': '{n} кроки',
  'gallery.steps.many': '{n} кроків',
  'gallery.steps.other': '{n} кроку',
  'gallery.current': 'Відкрито зараз',
  'account.changePassword': 'Змінити пароль',
  'account.newPassword': 'Новий пароль',
  'account.repeatPassword': 'Повтори новий пароль',
  'account.mismatch': 'Паролі не збігаються.',
  'account.passwordChanged': 'Пароль змінено.',
  'account.save': 'Зберегти',
  'account.cancel': 'Скасувати',
  'account.deleteTitle': 'Видалити акаунт',
  'account.deleteWarning':
    'Акаунт і всі твої сайти буде видалено одразу, разом з опублікованими — їхні посилання перестануть працювати. Цю дію не можна скасувати.',
  'account.deleteConfirm': 'Видалити все',
  'account.deleteFailed': 'Не вдалося видалити акаунт — спробуй ще раз.',
  'gallery.rename': 'Перейменувати',
  'gallery.renameLabel': 'Назва сайту',

  'signin.title': 'Увійди, щоб почати',
  'signin.intro': 'Твої сайти зберігаються в акаунті — вони чекатимуть тебе наступного разу.',
  'signin.submit': 'Увійти',
  'signin.toSignup': 'Створити акаунт',
  'signin.toForgot': 'Не пам’ятаю пароль',
  'signup.title': 'Створи акаунт',
  'signup.intro': 'Ми надішлемо код на пошту, щоб підтвердити адресу.',
  'signup.submit': 'Створити акаунт',
  'signup.toSignin': 'У мене вже є акаунт',
  'confirm.title': 'Перевір пошту',
  'confirm.submit': 'Підтвердити',
  'confirm.resend': 'Надіслати новий код',
  'forgot.title': 'Відновлення пароля',
  'forgot.intro': 'Ми надішлемо на пошту код, щоб задати новий пароль.',
  'forgot.submit': 'Надіслати код',
  'reset.title': 'Новий пароль',
  'reset.submit': 'Зберегти й увійти',
  'auth.back': 'Назад до входу',
  'auth.or': 'або',
  'auth.google': 'Увійти через Google',
  'auth.email': 'Email',
  'auth.password': 'Пароль',
  'auth.newPassword': 'Пароль (щонайменше 8 символів)',
  'auth.resetPassword': 'Новий пароль (щонайменше 8 символів)',
  'auth.code': 'Код з листа',
  'auth.notConfirmed': 'Пошту ще не підтверджено — ми надіслали новий код на {email}.',
  'auth.alreadyRegistered': 'Ця пошта вже зареєстрована — просто увійди.',
  'auth.codeSent': 'Ми надіслали код на {email}. Лист може йти до хвилини.',
  'auth.codeResent': 'Новий код надіслано на {email}.',
  'auth.resetSent': 'Якщо для {email} є акаунт, ми надіслали туди код.',
  'auth.invalidCredentials': 'Неправильна пошта або пароль.',
  'auth.badCode': 'Код неправильний або застарів — попроси новий.',
  'auth.weakPassword': 'Пароль закороткий — потрібно щонайменше 8 символів.',
  'auth.rateLimit': 'Забагато листів за короткий час — зачекай кілька хвилин і спробуй ще раз.',
  'auth.samePassword': 'Новий пароль має відрізнятися від старого.',
}

const dictionaries: Record<Lang, Record<Key, string>> = { en, uk }

/** Our own messages travel as keys; anything else is text from the server. */
export function isKey(text: string): text is Key {
  return Object.prototype.hasOwnProperty.call(en, text)
}

type Params = Record<string, string | number>

export type Translate = {
  (key: Key, params?: Params): string
  /** Count-dependent text: picks `${base}.one|few|many|other` by the language's rules. */
  plural: (base: 'gallery.steps', n: number) => string
  /** A message that came from the server (or Supabase) in English. */
  server: (text: string) => string
  lang: Lang
}

const LangContext = createContext<{ lang: Lang; setLang: (lang: Lang) => void }>({
  lang: 'en',
  setLang: () => {},
})

const STORAGE_KEY = 'vibeforge.lang'

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'uk' || saved === 'en') return saved
  } catch {
    // Storage can be blocked (private mode, strict settings) — just guess.
  }
  const preferred = navigator.languages?.length ? navigator.languages : [navigator.language]
  return preferred.some((l) => l?.toLowerCase().startsWith('uk')) ? 'uk' : 'en'
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  function setLang(next: Lang) {
    setLangState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Not remembered, but the switch still works for this visit.
    }
  }

  return <LangContext.Provider value={{ lang, setLang }}>{children}</LangContext.Provider>
}

export function useLang() {
  return useContext(LangContext)
}

export function useT(): Translate {
  const { lang } = useLang()
  const dict = dictionaries[lang]

  const t = ((key: Key, params?: Params) => fill(dict[key], params)) as Translate
  t.lang = lang
  t.plural = (base, n) => {
    const form = new Intl.PluralRules(lang).select(n) as 'one' | 'few' | 'many' | 'other'
    return fill(dict[`${base}.${form}` as Key] ?? dict[`${base}.other` as Key], { n })
  }
  t.server = (text) => (lang === 'en' ? text : serverToUk(text))
  return t
}

function fill(text: string, params?: Params): string {
  if (!params) return text
  return text.replace(/\{(\w+)\}/g, (match, name) =>
    name in params ? String(params[name]) : match,
  )
}

// The backend speaks English; these are all the messages it can show a
// person (see backend/app). Anything not listed stays in English.
const SERVER_UK: Record<string, string> = {
  'Prompt is empty': 'Запит порожній',
  'Unknown style': 'Невідомий стиль',
  'Project not found': 'Проєкт не знайдено',
  'Version not found': 'Версію не знайдено',
  'Name is too long (80 characters at most)': 'Назва задовга (щонайбільше 80 символів)',
  'Adding photos…': 'Додаю фото…',
  'The AI is busy right now — trying another model…': 'AI зараз зайнятий — пробую іншу модель…',
  'The AI dropped out halfway — starting over with another model…':
    'AI зупинився на півдорозі — починаю заново з іншою моделлю…',
  'All AI models are busy right now — please try again in a few minutes.':
    'Усі AI-моделі зараз зайняті — спробуй через кілька хвилин.',
  "VibeForge has used up today's free AI capacity for everyone — please try again tomorrow.":
    'VibeForge вичерпав безкоштовний ліміт AI на сьогодні для всіх користувачів — спробуй завтра.',
  "That doesn't look like this site's page": 'Це не схоже на сторінку цього сайту',
  'Sign in to continue': 'Увійди, щоб продовжити',
  'Sign-in service unavailable — try again': 'Сервіс входу недоступний — спробуй ще раз',
  'Session expired — sign in again': 'Сесія завершилась — увійди знову',
  'VibeForge has been updated — please refresh the page.': 'VibeForge оновився — онови сторінку.',
  '✎ Edited text by hand': '✎ Текст змінено вручну',
}

function serverToUk(text: string): string {
  if (text in SERVER_UK) return SERVER_UK[text]
  let m = text.match(/^You've used all (\d+) free generations for today — more tomorrow\.$/)
  if (m) return fill(uk['usage.limitReached'], { limit: m[1] })
  m = text.match(/^↩ Restored version (\d+)$/)
  if (m) return `↩ Повернуто версію ${m[1]}`
  return text
}
