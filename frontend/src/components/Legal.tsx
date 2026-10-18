// The two legal pages, /privacy and /terms, in English and Ukrainian. Plain
// text on purpose: they should say what the code actually does, so update
// them (both languages) whenever a new service or kind of data is added.

import type { ReactNode } from 'react'
import { useLang } from '../i18n'

const CONTACT = 'vibeforge.verify@gmail.com'
const UPDATED = { en: 'October 18, 2026', uk: '18 жовтня 2026 р.' }

const FRAME = {
  en: { back: '← Back to VibeForge', updated: 'Last updated:', contact: 'Contact', questions: 'Questions or requests:' },
  uk: { back: '← Назад до VibeForge', updated: 'Останнє оновлення:', contact: 'Контакти', questions: 'Питання чи запити:' },
}

function Page({ title, children }: { title: string; children: ReactNode }) {
  const { lang } = useLang()
  const f = FRAME[lang]
  return (
    <article className="legal card">
      <a href="/">{f.back}</a>
      <h2>{title}</h2>
      <p className="legal__updated">
        {f.updated} {UPDATED[lang]}
      </p>
      {children}
      <h3>{f.contact}</h3>
      <p>
        {f.questions} <a href={`mailto:${CONTACT}`}>{CONTACT}</a>
      </p>
    </article>
  )
}

export function Privacy() {
  const { lang } = useLang()
  return lang === 'uk' ? <PrivacyUk /> : <PrivacyEn />
}

export function Terms() {
  const { lang } = useLang()
  return lang === 'uk' ? <TermsUk /> : <TermsEn />
}

function PrivacyEn() {
  return (
    <Page title="Privacy Policy">
      <p>
        VibeForge is an independent project run by a single developer. It turns a text
        description into a one-page website. This page explains what data the service
        handles and why.
      </p>

      <h3>What we collect</h3>
      <ul>
        <li>
          <strong>Your account.</strong> Your email address. If you sign in with Google, also
          the name and profile picture Google shares. If you sign up with a password, it is
          stored only in hashed form; we never see it.
        </li>
        <li>
          <strong>What you create.</strong> The prompts you type and the websites generated
          from them, so your projects are there when you come back.
        </li>
        <li>
          <strong>Your photos.</strong> Photos you add to a site. Before sending them, your
          browser shrinks them (to 1600 pixels) and strips their metadata, including where
          they were taken; we store only that smaller copy. Photos are reachable at random,
          hard-to-guess links: anyone who has a link can see the photo, including visitors
          of a published site.
        </li>
        <li>
          <strong>Submissions from your sites.</strong> What visitors of your published sites
          send through forms (for example, a name, phone number or message). We store these
          submissions and, if you connected Telegram, forward them to you. This data belongs to
          you as the site owner: we only store and deliver it.
        </li>
        <li>
          <strong>Messages to support.</strong> If you write to us through “Support / Idea”, we
          store your message and your email address and forward the message to the VibeForge
          owner. They are deleted together with your account.
        </li>
        <li>
          <strong>Telegram.</strong> If you connect Telegram, we store the ID of your chat with
          the VibeForge bot so we can send submissions there.
        </li>
        <li>
          <strong>Visits to published sites.</strong> When someone opens a published site, we
          count the view for the site owner: we store the time and an anonymous code made from
          the visitor's IP address and browser. We do not store the IP address itself, and the
          code changes every day, so it can't identify a person or follow them from day to day.
          No cookies are used for this.
        </li>
        <li>
          <strong>Usage records.</strong> The time of each generation and which AI model made
          it. This is how the daily limit is counted.
        </li>
        <li>
          <strong>Technical logs.</strong> Like any website, our hosting providers record
          requests (including IP addresses) for security and troubleshooting.
        </li>
      </ul>
      <p>
        We do not use advertising or analytics trackers. Your browser stores a sign-in token
        so you stay signed in. Your browser also remembers the interface language you chose.
      </p>

      <h3>Who processes it</h3>
      <ul>
        <li><strong>Supabase</strong> stores accounts, projects and your photos (servers in the EU, Ireland).</li>
        <li><strong>Render</strong> runs our server (USA) and <strong>Vercel</strong> serves the site.</li>
        <li>
          <strong>Google Gemini</strong> generates the websites: your prompt, the current
          version of your site and the photos you add to a prompt are sent to Google. We use
          Google's free tier, where Google may use this content to improve its products and
          human reviewers may read it.{' '}
          <strong>
            Do not put personal or confidential information in prompts or photos (for
            example, documents).
          </strong>
        </li>
        <li><strong>Gmail</strong> sends the sign-in and password-reset codes.</li>
        <li><strong>Telegram</strong> delivers submissions to your chat with the VibeForge bot.</li>
        <li>
          <strong>Unsplash</strong> provides the photos: our server sends it only the short photo
          descriptions the AI writes (like "latte art on a wooden table"), never your account
          details. Generated and published sites load those photos from Unsplash's servers.
        </li>
      </ul>
      <p>We do not sell your data or share it with anyone else.</p>

      <h3>Published sites</h3>
      <p>
        When you publish a site, anyone with its link can see it, without signing in. Your name
        and email are not shown on it. Unpublish it or delete the project to take it down.
        The site owner sees how many views and visitors it had, but not who opened it.
      </p>

      <h3>How long we keep it</h3>
      <p>
        Until you delete it. You can delete any project in the app. To delete your whole
        account and everything in it, choose "Delete account" in the account menu —
        everything is deleted immediately, including published sites (their links stop
        working). This cannot be undone.
      </p>
      <p>
        Photos are deleted together with their site or account. A copy may stay in the content
        delivery network's cache for up to an hour, after which its link stops working. Photos
        you added but never sent are deleted automatically after a day.
      </p>
      <p>
        Submissions are deleted together with their site or account. You can disconnect
        Telegram at any time in the account menu or with the /stop command in the bot. Visit
        records are deleted together with their site or account.
      </p>

      <h3>Your rights</h3>
      <p>
        You can ask for a copy of your data, a correction, or deletion at any time by
        emailing us. If you are in the EU you also have the right to complain to your data
        protection authority.
      </p>

      <h3>Children</h3>
      <p>VibeForge is not intended for children under 16.</p>
    </Page>
  )
}

function PrivacyUk() {
  return (
    <Page title="Політика конфіденційності">
      <p>
        VibeForge — незалежний проєкт, який веде один розробник. Він перетворює текстовий опис
        на односторінковий сайт. Ця сторінка пояснює, які дані обробляє сервіс і навіщо.
      </p>

      <h3>Що ми збираємо</h3>
      <ul>
        <li>
          <strong>Ваш акаунт.</strong> Ваша адреса електронної пошти. Якщо ви входите через
          Google — також ім’я та фото профілю, якими ділиться Google. Якщо ви реєструєтеся з
          паролем, він зберігається лише в захешованому вигляді; ми ніколи його не бачимо.
        </li>
        <li>
          <strong>Те, що ви створюєте.</strong> Запити, які ви вводите, і сайти, створені за
          ними, — щоб ваші проєкти були на місці, коли ви повернетеся.
        </li>
        <li>
          <strong>Ваші фото.</strong> Фото, які ви додаєте до сайту. Перед відправкою браузер
          зменшує їх (до 1600 пікселів) і прибирає з них службові дані, зокрема місце зйомки;
          ми зберігаємо лише цю зменшену копію. Фото доступні за випадковими посиланнями, які
          важко вгадати: побачити їх може той, у кого є посилання, зокрема відвідувачі
          опублікованого сайту.
        </li>
        <li>
          <strong>Заявки з ваших сайтів.</strong> Те, що відвідувачі ваших опублікованих сайтів
          надсилають через форми (наприклад, ім’я, телефон, повідомлення). Ми зберігаємо ці
          заявки і, якщо ви підключили Telegram, пересилаємо їх вам. Ці дані належать вам як
          власнику сайту: ми лише зберігаємо й доставляємо їх.
        </li>
        <li>
          <strong>Повідомлення в підтримку.</strong> Якщо ви пишете нам через «Підтримка / Ідея»,
          ми зберігаємо ваше повідомлення та адресу пошти й пересилаємо повідомлення власнику
          VibeForge. Вони видаляються разом із вашим акаунтом.
        </li>
        <li>
          <strong>Telegram.</strong> Якщо ви підключаєте Telegram, ми зберігаємо ідентифікатор
          вашого чату з ботом VibeForge, щоб надсилати туди заявки.
        </li>
        <li>
          <strong>Відвідування опублікованих сайтів.</strong> Коли хтось відкриває опублікований
          сайт, ми рахуємо перегляд для власника сайту: зберігаємо час і анонімний код,
          створений з IP-адреси та браузера відвідувача. Саму IP-адресу ми не зберігаємо, а код
          змінюється щодня, тож за ним не можна визначити людину чи стежити за нею з дня на
          день. Файли cookie для цього не використовуються.
        </li>
        <li>
          <strong>Записи про використання.</strong> Час кожної генерації та те, яка AI-модель її
          зробила. Так рахується денний ліміт.
        </li>
        <li>
          <strong>Технічні журнали.</strong> Як і на будь-якому сайті, наші хостинг-провайдери
          записують запити (зокрема IP-адреси) для безпеки та усунення збоїв.
        </li>
      </ul>
      <p>
        Ми не використовуємо рекламні чи аналітичні трекери. Ваш браузер зберігає токен входу,
        щоб ви залишалися в акаунті. Також браузер запам’ятовує вибрану вами мову інтерфейсу.
      </p>

      <h3>Хто обробляє дані</h3>
      <ul>
        <li><strong>Supabase</strong> зберігає акаунти, проєкти й ваші фото (сервери в ЄС, Ірландія).</li>
        <li><strong>Render</strong> запускає наш сервер (США), а <strong>Vercel</strong> віддає сайт.</li>
        <li>
          <strong>Google Gemini</strong> створює сайти: ваш запит, поточна версія вашого сайту та
          фото, які ви додали до запиту, надсилаються в Google. Ми користуємося безкоштовним
          рівнем Google, на якому Google може використовувати цей вміст для покращення своїх
          продуктів, а читати його можуть люди-рецензенти.{' '}
          <strong>
            Не вказуйте в запитах і не додавайте на фото особисту чи конфіденційну інформацію
            (наприклад, документи).
          </strong>
        </li>
        <li><strong>Gmail</strong> надсилає коди для входу та відновлення пароля.</li>
        <li><strong>Telegram</strong> доставляє заявки у ваш чат із ботом VibeForge.</li>
        <li>
          <strong>Unsplash</strong> надає фото: наш сервер надсилає йому лише короткі описи фото,
          які пише AI (наприклад, «latte art on a wooden table»), і ніколи — дані вашого акаунта.
          Створені й опубліковані сайти завантажують ці фото із серверів Unsplash.
        </li>
      </ul>
      <p>Ми не продаємо ваші дані й не передаємо їх нікому іншому.</p>

      <h3>Опубліковані сайти</h3>
      <p>
        Коли ви публікуєте сайт, його може побачити будь-хто, у кого є посилання, без входу в
        акаунт. Ваше ім’я та пошта на ньому не показуються. Щоб прибрати сайт, зніміть його з
        публікації або видаліть проєкт. Власник сайту бачить кількість переглядів і відвідувачів,
        але не бачить, хто саме відкривав сайт.
      </p>

      <h3>Як довго ми зберігаємо дані</h3>
      <p>
        Доки ви їх не видалите. Будь-який проєкт можна видалити в застосунку. Щоб видалити весь
        акаунт і все, що в ньому, натисніть «Видалити акаунт» у меню акаунта — усе буде видалено
        одразу, разом з опублікованими сайтами (їхні посилання перестануть працювати). Цю дію не
        можна скасувати.
      </p>
      <p>
        Фото видаляються разом із сайтом або акаунтом. Копія фото може ще до години залишатися
        в кеші мережі доставки (CDN), після чого посилання на нього перестає працювати. Фото,
        які ви додали, але так і не надіслали, видаляються автоматично через добу.
      </p>
      <p>
        Заявки видаляються разом із сайтом або акаунтом. Відключити Telegram можна будь-коли в
        меню акаунта або командою /stop у боті. Записи про відвідування видаляються разом із
        сайтом або акаунтом.
      </p>

      <h3>Ваші права</h3>
      <p>
        Ви можете будь-коли попросити копію своїх даних, їх виправлення чи видалення, написавши
        нам. Якщо ви перебуваєте в ЄС, ви також маєте право подати скаргу до свого органу із
        захисту даних.
      </p>

      <h3>Діти</h3>
      <p>VibeForge не призначений для дітей віком до 16 років.</p>
    </Page>
  )
}

function TermsEn() {
  return (
    <Page title="Terms of Service">
      <p>By using VibeForge you agree to these terms.</p>

      <h3>The service</h3>
      <p>
        VibeForge generates one-page websites from text descriptions using AI. It is a free
        service in early development, provided as is: it may be slow, unavailable, or change
        at any time, and limits (currently 5 generations per day) may change.
      </p>

      <h3>What you create</h3>
      <p>
        The websites you generate are yours to use. AI output can contain mistakes and may
        resemble what other people generate, so review a site before you publish it. You are
        responsible for how you use it.
      </p>
      <p>
        By adding photos you confirm that you have the right to use them (for example, they
        are yours, or a client agreed to it) and that they contain nothing illegal.
      </p>

      <h3>Forms on your sites</h3>
      <p>
        If your published site has a form, you are collecting its visitors' data and are
        responsible for it: tell them who you are and why you need it. Do not use forms to
        collect passwords, payment details or other sensitive information.
      </p>

      <h3>Rules</h3>
      <ul>
        <li>Do not generate illegal content, phishing or scam pages, malware, or sites that impersonate real people or organisations.</li>
        <li>Do not try to get around the limits, for example with multiple accounts.</li>
        <li>Do not attack or overload the service.</li>
      </ul>
      <p>We may suspend accounts that break these rules.</p>

      <h3>Liability</h3>
      <p>
        To the extent the law allows, VibeForge is not liable for losses resulting from the
        use of the service or of the websites it generates.
      </p>

      <h3>Changes</h3>
      <p>
        We may update these terms; the date at the top shows the latest version. See also
        our <a href="/privacy">Privacy Policy</a>.
      </p>
    </Page>
  )
}

function TermsUk() {
  return (
    <Page title="Умови використання">
      <p>Користуючись VibeForge, ви погоджуєтеся з цими умовами.</p>

      <h3>Сервіс</h3>
      <p>
        VibeForge створює односторінкові сайти з текстових описів за допомогою AI. Це
        безкоштовний сервіс на ранньому етапі розробки, що надається «як є»: він може працювати
        повільно, бути недоступним або змінитися будь-коли, а ліміти (зараз 5 генерацій на день)
        можуть змінюватися.
      </p>

      <h3>Те, що ви створюєте</h3>
      <p>
        Створені вами сайти належать вам для використання. Результат роботи AI може містити
        помилки й бути схожим на те, що створюють інші люди, тож перевірте сайт перед
        публікацією. Ви відповідаєте за те, як його використовуєте.
      </p>
      <p>
        Додаючи фото, ви підтверджуєте, що маєте право їх використовувати (наприклад, це ваші
        фото або фото клієнта, який на це погодився) і що на них немає незаконного вмісту.
      </p>

      <h3>Форми на ваших сайтах</h3>
      <p>
        Якщо на вашому опублікованому сайті є форма, ви збираєте дані відвідувачів і
        відповідаєте за це: повідомте їм, хто ви і навіщо вам ці дані. Не використовуйте форми
        для збору паролів, платіжних даних чи іншої чутливої інформації.
      </p>

      <h3>Правила</h3>
      <ul>
        <li>Не створюйте незаконний вміст, фішингові чи шахрайські сторінки, шкідливе ПЗ або сайти, що видають себе за реальних людей чи організації.</li>
        <li>Не намагайтеся обійти ліміти, наприклад за допомогою кількох акаунтів.</li>
        <li>Не атакуйте сервіс і не перевантажуйте його.</li>
      </ul>
      <p>Ми можемо призупинити акаунти, що порушують ці правила.</p>

      <h3>Відповідальність</h3>
      <p>
        Наскільки це дозволяє закон, VibeForge не несе відповідальності за збитки, спричинені
        використанням сервісу чи створених ним сайтів.
      </p>

      <h3>Зміни</h3>
      <p>
        Ми можемо оновлювати ці умови; дата вгорі показує останню версію. Див. також нашу{' '}
        <a href="/privacy">Політику конфіденційності</a>.
      </p>
    </Page>
  )
}
