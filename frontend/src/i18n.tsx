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
  'telegram.title': '🔔 Telegram: form submissions and making sites',
  'telegram.connect': 'Connect Telegram',
  'telegram.waiting': 'Press Start in Telegram…',
  'telegram.connected': '✓ Connected',
  'telegram.connectedHint': 'Write the bot what site you need and it makes it.',
  'telegram.disconnect': 'Disconnect',
  'telegram.hint': 'Forms on this site can send submissions straight to your Telegram — connect it in the account menu.',
  'telegram.republish': 'Press “Update” so forms on this site send submissions to your Telegram.',
  'app.stats': '📊 Stats',
  'stats.back': '← Back to VibeForge',
  'stats.title': 'Stats',
  'stats.forbidden': 'Only the owner can see this page.',
  'stats.users': 'Users',
  'stats.usersDetail': '+{new} this week · {active} active this week',
  'stats.sites': 'Sites',
  'stats.sitesDetail': '{published} published',
  'stats.generations': 'Generations',
  'stats.generationsToday': 'Generations today',
  'stats.generationsDetail': '{week} this week · {month} in 30 days · {total} in all',
  'stats.photos': 'Own photos',
  'stats.models': 'AI models this week',
  'stats.people': 'Users',
  'stats.email': 'Email',
  'stats.lastActive': 'Last active',
  'stats.you': 'you',
  'stats.note': 'Emails are partly hidden. Failed generations are not counted.',
  'footer.privacy': 'Privacy',
  'footer.terms': 'Terms',
  'footer.unsplash': 'Photos by Unsplash',

  'usage.label': 'Left today',
  'usage.count': '{left} of {limit}',
  'usage.none': 'No generations left today',
  'usage.limitReached': "You've used all {limit} free generations for today — more tomorrow.",

  'chat.newSite': 'New site',
  'chat.newSiteButton': '+ New site',
  'chat.empty': 'Describe your site, or start from an idea:',
  'chat.labelNew': 'What site shall we make?',
  'chat.labelEdit': 'What should change?',
  'chat.placeholderNew': 'e.g. a landing page for a coffee shop with a menu',
  'chat.placeholderEdit': 'e.g. make the buttons darker',
  'chat.send': 'Create site',
  'chat.sendEdit': 'Apply changes',
  'chat.sending': 'Building…',
  'chat.style': 'Site style',
  'review.title': '💬 Client review',
  'review.titleCount': '💬 Client review · {n} open',
  'review.intro': 'Send the link to your client: they see the site as it is now and leave comments right on the page — no account needed.',
  'review.start': 'Create a link for the client',
  'review.linkLabel': 'Client link:',
  'review.stop': 'Switch off',
  'review.stopHint': 'The link stops working; the comments stay.',
  'review.none': 'No comments yet.',
  'review.client': 'Client',
  'review.resolve': '✓ Done',
  'review.reopen': 'Reopen',
  'review.delete': 'Delete',
  'rv.title': 'Review: {name}',
  'rv.intro': 'Click anything on the page and write what should change. The owner gets your comment.',
  'rv.modeOn': '💬 Comment mode: on (clicks add comments)',
  'rv.modeOff': '👀 Comment mode: off (the site works normally)',
  'rv.name': 'Your name (optional)',
  'rv.about': 'About: “{label}”',
  'rv.placeholder': 'What should change here?',
  'rv.send': 'Send comment',
  'rv.sending': 'Sending…',
  'rv.list': 'Comments',
  'rv.empty': 'No comments yet — click something on the page.',
  'rv.done': 'done',
  'rv.show': 'Show on the page',
  'rv.notFound': "This link doesn't work — ask the owner for a new one.",
  'rv.loading': 'Loading…',
  'chat.bilingual': '🌐 Two languages: UK + EN',
  'chat.bilingualHint': 'The site gets a Ukrainian and an English version with a language switcher',
  'actions.addLanguage': '🌐 Add 2nd language',
  'actions.addLanguageHint': 'Makes the site Ukrainian + English with a switcher — uses one of your tries',
  'lang.addPrompt': 'Make this site bilingual: Ukrainian and English, with a language switcher.',
  'edit.siteLanguage': 'Site language:',
  'chat.multipage': '📑 Several pages',
  'chat.multipageHint': 'The site gets separate pages (Home, About, Contact…) with a menu',
  'actions.addPages': '📑 Add pages',
  'actions.addPagesHint': 'Splits the site into several pages with a menu — uses one of your tries',
  'pages.addPrompt': 'Make this site multi-page: spread the content over separate pages (Home, About, Contact and so on) with a menu.',
  'edit.sitePage': 'Page:',
  'chat.mascot': 'Spark, the VibeForge helper',
  'examples.title': 'Ideas to start from',
  'examples.cafe': '☕ Café',
  'examples.cafePrompt':
    'A site for a cosy café called “Grain”: a hero with a photo of coffee, a menu with prices (coffee, desserts, breakfasts), about us, guest reviews, opening hours and contacts.',
  'examples.photographer': '📷 Photographer',
  'examples.photographerPrompt':
    'A portfolio for Helen, a wedding photographer: a big hero, a gallery of her work where photos open full screen, packages with prices, reviews from couples and a booking form.',
  'examples.guesthouse': '🏡 Guesthouse',
  'examples.guesthousePrompt':
    'A site for a family guesthouse in the mountains: rooms with prices per night, a price calculator for the stay, things to do in summer and winter, a gallery, frequently asked questions and a booking form.',
  'examples.salon': '💇 Beauty salon',
  'examples.salonPrompt':
    'A site for the “Lavender” beauty salon: services with prices (haircuts, manicure, facials), the stylists with photos, reviews, booking through a form, and contacts.',
  'examples.trainer': '🏋️ Personal trainer',
  'examples.trainerPrompt':
    'A landing page for Andrew, a personal trainer: training programmes with prices, client results, a class schedule, answers to common questions and a button to book a free first session.',

  'progress.starting': 'Spark is getting started…',
  'progress.writing': 'Spark is writing your site… {kb} KB',
  'progress.generating': 'Spark is working…',

  'reply.done': 'Done! What shall we change next?',
  'reply.doneEarlier': 'Done.',
  'reply.restored': 'Done — that version is back.',
  'reply.saved': 'Saved your changes.',
  'reply.error': 'Error: {detail}',
  'photos.add': 'Add photos',
  'photos.hint': 'Your own photos, up to {max} per site — you can also paste (Ctrl/⌘+V) or drag them in',
  'photos.drop': 'Drop photos here',
  'photos.counter': '{n} of {max} photos — say where to put them',
  'photos.uploading': 'Uploading…',
  'photos.remove': 'Remove photo',
  'photos.tooLarge': 'That file is too large (10 MB at most).',
  'photos.unsupported': "This browser can't open that file — try a JPEG or PNG.",
  'photos.unused': "Some of your photos didn't make it onto the site: {list}. Tell me where to put them.",
  'photos.count.one': '{n} photo',
  'photos.count.few': '{n} photos',
  'photos.count.many': '{n} photos',
  'photos.count.other': '{n} photos',

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
  'preview.device': 'Preview size',
  'preview.desktop': '🖥 Computer',
  'preview.phone': '📱 Phone',
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
  'editing.hint': 'Click any text on the page to change it. Click a photo, button or block to change its color, photo or link. Buttons and menus on the site are paused while you edit.',
  'edit.pick': 'Click something on the page — text, a photo, a button or a block — to change it.',
  'edit.selected': 'Selected: “{label}”',
  'edit.textColor': 'Text color',
  'edit.background': 'Background',
  'edit.replacePhoto': '🖼 Replace photo',
  'edit.uploading': 'Uploading…',
  'edit.link': 'Link address',
  'edit.linkBad': "That kind of link isn't allowed.",
  'edit.setLink': 'Set link',
  'edit.wider': '↑ Bigger block',
  'edit.widerHint': 'Select the block this element is inside',
  'edit.undo': '↶ Undo',
  'editing.save': 'Save changes',
  'editing.saving': 'Saving…',
  'editing.cancel': 'Cancel',

  'visits.none': '👁 No visits yet — share the link or the QR code.',
  'visits.line': '👁 Views today: {today} · this week: {week} (people: {people}) · all time: {total}',
  'qr.button': 'QR code',
  'qr.title': 'QR code for your site',
  'qr.alt': 'QR code that opens {url}',
  'qr.hint': 'Print it for tables, a shop window or flyers — a phone camera opens your site straight away.',
  'qr.download': 'Download PNG',
  'actions.editText': 'Edit site',
  'actions.editTextHint': 'Change text, colors, photos and links yourself — free, no AI',
  'actions.history': 'History',
  'actions.hideHistory': 'Hide history',
  'actions.download': 'Download',
  'actions.publish': 'Publish',
  'actions.publishing': 'Publishing…',
  'seo.label': 'Show this site in Google search',
  'seo.on': 'Google can now find it — but only after it visits the page, which can take days or weeks. A search for the site name works best.',
  'seo.off': 'Off: search engines are asked to skip the page, only people with the link see it.',
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
  'feedback.title': 'Support / Idea',
  'feedback.intro': 'Found a problem or have an idea? Write to me — I read every message.',
  'feedback.idea': '💡 Idea',
  'feedback.problem': '🐞 Problem',
  'feedback.question': '❓ Question',
  'feedback.placeholder': 'Your message…',
  'feedback.send': 'Send',
  'feedback.sent': 'Thank you! The message has been sent.',
  'feedback.failed': 'Could not send — please try again.',
  'feedback.tooMany': 'Too many messages in a row — please try again later.',
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
  'telegram.title': '🔔 Telegram: заявки та створення сайтів',
  'telegram.connect': 'Підключити Telegram',
  'telegram.waiting': 'Натисни Start у Telegram…',
  'telegram.connected': '✓ Підключено',
  'telegram.connectedHint': 'Напиши боту, який сайт потрібен, — він його створить.',
  'telegram.disconnect': 'Відключити',
  'telegram.hint': 'Заявки з форми цього сайту можуть приходити тобі в Telegram — підключи його в меню акаунта.',
  'telegram.republish': 'Натисни «Оновити», щоб заявки з форми цього сайту приходили тобі в Telegram.',
  'app.stats': '📊 Статистика',
  'stats.back': '← Назад до VibeForge',
  'stats.title': 'Статистика',
  'stats.forbidden': 'Цю сторінку бачить лише власник.',
  'stats.users': 'Користувачі',
  'stats.usersDetail': '+{new} за тиждень · {active} активних за тиждень',
  'stats.sites': 'Сайти',
  'stats.sitesDetail': '{published} опубліковано',
  'stats.generations': 'Генерації',
  'stats.generationsToday': 'Генерацій сьогодні',
  'stats.generationsDetail': '{week} за тиждень · {month} за 30 днів · {total} усього',
  'stats.photos': 'Власні фото',
  'stats.models': 'AI-моделі за тиждень',
  'stats.people': 'Користувачі',
  'stats.email': 'Пошта',
  'stats.lastActive': 'Остання активність',
  'stats.you': 'ти',
  'stats.note': 'Пошту частково приховано. Невдалі генерації не враховуються.',
  'footer.privacy': 'Конфіденційність',
  'footer.terms': 'Умови',
  'footer.unsplash': 'Фото з Unsplash',

  'usage.label': 'Залишилось',
  'usage.count': '{left} з {limit}',
  'usage.none': 'На сьогодні все',
  'usage.limitReached': 'Безкоштовні генерації на сьогодні закінчились ({limit} з {limit}) — нові з’являться завтра.',

  'chat.newSite': 'Новий сайт',
  'chat.newSiteButton': '+ Новий сайт',
  'chat.empty': 'Опиши свій сайт або почни з ідеї:',
  'chat.labelNew': 'Який сайт створимо?',
  'chat.labelEdit': 'Що змінити?',
  'chat.placeholderNew': 'наприклад: лендинг для кав’ярні з меню',
  'chat.placeholderEdit': 'наприклад: зроби кнопки темнішими',
  'chat.send': 'Створити сайт',
  'chat.sendEdit': 'Внести зміни',
  'chat.sending': 'Створюю…',
  'chat.style': 'Стиль сайту',
  'review.title': '💬 Перегляд клієнтом',
  'review.titleCount': '💬 Перегляд клієнтом · відкрито: {n}',
  'review.intro': 'Надішли клієнту посилання: він побачить сайт таким, яким він зараз, і залишить коментарі прямо на сторінці — без реєстрації.',
  'review.start': 'Створити посилання для клієнта',
  'review.linkLabel': 'Посилання для клієнта:',
  'review.stop': 'Вимкнути',
  'review.stopHint': 'Посилання перестане працювати; коментарі залишаться.',
  'review.none': 'Коментарів ще немає.',
  'review.client': 'Клієнт',
  'review.resolve': '✓ Виконано',
  'review.reopen': 'Відновити',
  'review.delete': 'Видалити',
  'rv.title': 'Перегляд: {name}',
  'rv.intro': 'Клацни на будь-що на сторінці й напиши, що змінити. Власник отримає твій коментар.',
  'rv.modeOn': '💬 Режим коментарів: увімкнено (клік додає коментар)',
  'rv.modeOff': '👀 Режим коментарів: вимкнено (сайт працює як звичайно)',
  'rv.name': 'Твоє ім’я (необов’язково)',
  'rv.about': 'Про: «{label}»',
  'rv.placeholder': 'Що тут змінити?',
  'rv.send': 'Надіслати коментар',
  'rv.sending': 'Надсилаю…',
  'rv.list': 'Коментарі',
  'rv.empty': 'Коментарів ще немає — клацни на щось на сторінці.',
  'rv.done': 'виконано',
  'rv.show': 'Показати на сторінці',
  'rv.notFound': 'Це посилання не працює — попроси у власника нове.',
  'rv.loading': 'Завантажую…',
  'chat.bilingual': '🌐 Дві мови: УКР + ENG',
  'chat.bilingualHint': 'Сайт матиме українську й англійську версії з перемикачем мови',
  'actions.addLanguage': '🌐 Додати другу мову',
  'actions.addLanguageHint': 'Зробить сайт українським + англійським з перемикачем — витратить одну спробу',
  'lang.addPrompt': 'Зроби цей сайт двомовним: українська й англійська, з перемикачем мов.',
  'edit.siteLanguage': 'Мова сайту:',
  'chat.multipage': '📑 Кілька сторінок',
  'chat.multipageHint': 'Сайт матиме окремі сторінки (Головна, Про нас, Контакти…) з меню',
  'actions.addPages': '📑 Додати сторінки',
  'actions.addPagesHint': 'Розділить сайт на кілька сторінок з меню — витратить одну спробу',
  'pages.addPrompt': 'Зроби цей сайт багатосторінковим: розподіли вміст по окремих сторінках (Головна, Про нас, Контакти тощо) з меню.',
  'edit.sitePage': 'Сторінка:',
  'chat.mascot': 'Іскра, помічниця VibeForge',
  'examples.title': 'Ідеї для початку',
  'examples.cafe': '☕ Кав’ярня',
  'examples.cafePrompt':
    'Сайт для затишної кав’ярні «Зерно»: головний екран із фото кави, меню з цінами (кава, десерти, сніданки), про нас, відгуки гостей, години роботи й контакти.',
  'examples.photographer': '📷 Фотограф',
  'examples.photographerPrompt':
    'Портфоліо весільної фотографині Олени: великий головний екран, галерея робіт, де фото відкриваються на весь екран, пакети послуг із цінами, відгуки пар і форма заявки.',
  'examples.guesthouse': '🏡 Садиба',
  'examples.guesthousePrompt':
    'Сайт сімейної садиби в горах: номери з цінами за ніч, калькулятор вартості проживання, чим зайнятися влітку й узимку, галерея, часті питання і форма бронювання.',
  'examples.salon': '💇 Салон краси',
  'examples.salonPrompt':
    'Сайт салону краси «Лаванда»: послуги з цінами (стрижки, манікюр, догляд за обличчям), майстри з фото, відгуки, запис через форму і контакти.',
  'examples.trainer': '🏋️ Тренер',
  'examples.trainerPrompt':
    'Лендинг персонального тренера Андрія: програми тренувань із цінами, результати клієнтів, розклад занять, відповіді на часті питання і кнопка запису на перше безкоштовне заняття.',

  'progress.starting': 'Іскра береться до роботи…',
  'progress.writing': 'Іскра пише сайт… {kb} КБ',
  'progress.generating': 'Іскра працює…',

  'reply.done': 'Готово! Що змінимо далі?',
  'reply.doneEarlier': 'Готово.',
  'reply.restored': 'Готово — цю версію повернуто.',
  'reply.saved': 'Зміни збережено.',
  'reply.error': 'Помилка: {detail}',
  'photos.add': 'Додати фото',
  'photos.hint': 'Свої фото, до {max} на сайт — можна також вставити (Ctrl/⌘+V) або перетягнути сюди',
  'photos.drop': 'Відпусти фото тут',
  'photos.counter': '{n} з {max} фото — напиши, куди їх поставити',
  'photos.uploading': 'Завантажую…',
  'photos.remove': 'Прибрати фото',
  'photos.tooLarge': 'Файл завеликий (щонайбільше 10 МБ).',
  'photos.unsupported': 'Цей браузер не може відкрити такий файл — спробуй JPEG або PNG.',
  'photos.unused': 'Не всі твої фото потрапили на сайт: {list}. Напиши, куди їх поставити.',
  'photos.count.one': '{n} фото',
  'photos.count.few': '{n} фото',
  'photos.count.many': '{n} фото',
  'photos.count.other': '{n} фото',

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
  'preview.device': 'Розмір перегляду',
  'preview.desktop': '🖥 Комп’ютер',
  'preview.phone': '📱 Телефон',
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
  'editing.hint': 'Клацни на будь-який текст на сторінці, щоб змінити його. Клацни на фото, кнопку чи блок — і зміниш колір, фото або посилання. Кнопки й меню сайту на паузі, поки ти редагуєш.',
  'edit.pick': 'Клацни на щось на сторінці — текст, фото, кнопку чи блок, — щоб змінити.',
  'edit.selected': 'Вибрано: «{label}»',
  'edit.textColor': 'Колір тексту',
  'edit.background': 'Фон',
  'edit.replacePhoto': '🖼 Замінити фото',
  'edit.uploading': 'Завантажую…',
  'edit.link': 'Адреса посилання',
  'edit.linkBad': 'Таке посилання не підходить.',
  'edit.setLink': 'Задати посилання',
  'edit.wider': '↑ Більший блок',
  'edit.widerHint': 'Вибрати блок, у якому лежить цей елемент',
  'edit.undo': '↶ Скасувати',
  'editing.save': 'Зберегти зміни',
  'editing.saving': 'Зберігаю…',
  'editing.cancel': 'Скасувати',

  'visits.none': '👁 Ще ніхто не відкривав — поділися посиланням або QR-кодом.',
  'visits.line': '👁 Переглядів сьогодні: {today} · за тиждень: {week} (людей: {people}) · усього: {total}',
  'qr.button': 'QR-код',
  'qr.title': 'QR-код твого сайту',
  'qr.alt': 'QR-код, що відкриває {url}',
  'qr.hint': 'Надрукуй його для столиків, вітрини чи флаєрів — камера телефона одразу відкриє твій сайт.',
  'qr.download': 'Завантажити PNG',
  'actions.editText': 'Редагувати сайт',
  'actions.editTextHint': 'Зміни текст, кольори, фото й посилання сам — безкоштовно, без AI',
  'actions.history': 'Історія',
  'actions.hideHistory': 'Сховати історію',
  'actions.download': 'Завантажити',
  'actions.publish': 'Опублікувати',
  'actions.publishing': 'Публікую…',
  'seo.label': 'Показувати цей сайт у пошуку Google',
  'seo.on': 'Google може знайти сайт, але лише після того, як відвідає сторінку, — це може зайняти дні чи тижні. Найкраще шукається за назвою сайту.',
  'seo.off': 'Вимкнено: пошуковики не показують сторінку, її бачать лише ті, хто має посилання.',
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
  'feedback.title': 'Підтримка / Ідея',
  'feedback.intro': 'Знайшов помилку чи маєш ідею? Напиши мені — я читаю кожне повідомлення.',
  'feedback.idea': '💡 Ідея',
  'feedback.problem': '🐞 Проблема',
  'feedback.question': '❓ Питання',
  'feedback.placeholder': 'Твоє повідомлення…',
  'feedback.send': 'Надіслати',
  'feedback.sent': 'Дякую! Повідомлення надіслано.',
  'feedback.failed': 'Не вдалося надіслати — спробуй ще раз.',
  'feedback.tooMany': 'Забагато повідомлень підряд — спробуй пізніше.',
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
  plural: (base: 'gallery.steps' | 'photos.count', n: number) => string
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
  'Photo not found': 'Фото не знайдено',
  'Comment is empty': 'Коментар порожній',
  'Comment is too long': 'Коментар задовгий',
  'Too many comments — please try again later': 'Забагато коментарів — спробуй пізніше',
  "This link doesn't exist or was switched off": 'Це посилання не існує або вимкнене',
  "Telegram isn't available right now": 'Telegram зараз недоступний',
  'Too many messages — please try again later': 'Забагато повідомлень — спробуй пізніше',
  'Only the owner can see this': 'Це бачить лише власник',
  "That file isn't a photo we can use (JPEG, PNG or WebP)": 'Цей файл не підходить — потрібне фото JPEG, PNG або WebP',
  'That photo is too large': 'Фото завелике',
  "You've reached the photo limit for your account": 'Досягнуто ліміту фото для твого акаунта',
  'Sign in to continue': 'Увійди, щоб продовжити',
  'Sign-in service unavailable — try again': 'Сервіс входу недоступний — спробуй ще раз',
  'Session expired — sign in again': 'Сесія завершилась — увійди знову',
  'VibeForge has been updated — please refresh the page.': 'VibeForge оновився — онови сторінку.',
  '✎ Edited text by hand': '✎ Текст змінено вручну',
  '✎ Edited by hand': '✎ Змінено вручну',
}

function serverToUk(text: string): string {
  if (text in SERVER_UK) return SERVER_UK[text]
  let m = text.match(/^You've used all (\d+) free generations for today — more tomorrow\.$/)
  if (m) return fill(uk['usage.limitReached'], { limit: m[1] })
  m = text.match(/^You can add up to (\d+) photos per site$/)
  if (m) return `Можна додати щонайбільше ${m[1]} фото на сайт`
  m = text.match(/^↩ Restored version (\d+)$/)
  if (m) return `↩ Повернуто версію ${m[1]}`
  return text
}
