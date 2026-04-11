# Content Authoring Guide — How to Fill the Knowledge Base and Files

**Audience:** admins adding or editing entries in the admin panel
([admin.py](../admin.py)).
**Goal:** make every entry findable by vector search and usable by the LLM so
the bot gives complete, correct answers.

If you only read one section, read **"The 60-Second Mental Model"** and the
**Checklist** at the end.

---

## 1. The 60-Second Mental Model

A student asks the bot a question. The bot:

1. **Embeds the question** with the `intfloat/multilingual-e5-base` model
   (768-dim vector, multilingual — Russian, Kazakh, English).
2. **Finds the 3 nearest knowledge entries** by cosine distance. Entries with
   distance `> 0.35` are dropped.
3. **Builds a context block** from the passing entries and gives it to the LLM
   with a strict instruction: *answer ONLY from this text, never invent
   anything*. If the context is empty, the bot refuses — no LLM call.
4. **Attaches files** in two ways:
   - **Curated (primary)** — any file an admin explicitly linked to a matched
     knowledge entry is always attached. No thresholds, no guessing.
   - **Vector fallback** — a file whose `keywords` overlap the query AND whose
     distance ≤ 0.20 AND which is a clear winner (gap ≥ 0.05 to next
     keyword-matching file).

Two consequences that shape everything below:

- **The LLM never sees the question — only the context you wrote.** If your
  entry is missing a step, a deadline, or a contact, the bot cannot recover it.
- **The embedding model only sees text.** For files, that means
  `title + caption + keywords + category` — it *cannot* read PDFs or photos.
  Describe the file's content in those fields or the file is invisible.

---

## 2. What Actually Gets Embedded

Every entry is converted to this canonical string before embedding
([services/embeddings.py:16-35](../services/embeddings.py#L16-L35)):

```
Title: <title>. Category: <category>. Keywords: <kw1, kw2, ...>. Content: <content>
```

Sections with empty values are omitted. Then the string is prefixed with
`passage: ` (for stored items) or `query: ` (for user questions) — this is an
E5-specific convention that significantly improves retrieval quality.

**Why the format matters:** the model sees one long sentence. Filling in all
four fields gives the embedding multiple "handles" — a question that phrases
things via the title, another via keywords, another via content wording — all
map to roughly the same vector neighborhood.

---

## 3. Knowledge Entries — Field Reference

### 3.1 `title` (optional but highly recommended)

A short, distinctive noun phrase. 2–8 words.

- ✅ `Льготная стипендия для социально уязвимых студентов`
- ✅ `Процедура Add/Drop (замена дисциплин)`
- ✅ `Военная кафедра — условия поступления`
- ❌ `Информация` (tells you nothing)
- ❌ `Стипендии КБТУ: виды, условия получения, размер выплат и порядок подачи заявления через WSP` (too long — that's the content's job)

The title is the strongest single signal for the embedding — make it the
phrase you'd want a student to type as a query.

### 3.2 `content` (required)

**This is the only text the LLM will see.** The system prompt is strict:
*answer exclusively from `<knowledge>`*. If the content doesn't say it, the bot
cannot say it.

**Write a complete, self-contained answer.** Cover whichever of the "seven Ws"
apply:

| W | Example |
|---|---|
| **What** is it | "Add/Drop is the first week of the semester when students can add, drop, or replace courses." |
| **Who** is eligible | "All bachelor students; master's students follow a different rule." |
| **Where** to go / which portal | "Submitted via WSP → Academic → Add/Drop request." |
| **When** — deadlines, dates | "Requests accepted until 13:00 on the Friday of the first week." |
| **How** — step-by-step | "1. Log into WSP. 2. Open Add/Drop. 3. Pick a course. ..." |
| **How much** — fees | "Retake of one course costs 35 000 ₸." |
| **Who to contact** — phone/email/office | "Office of the Registrar, room C-114, registrar@kbtu.kz." |

**Length:** as long as the answer needs. 200–800 characters is typical. Don't
pad. Don't compress. If the answer needs steps, use a numbered list — the LLM
preserves that structure.

**Language:** write in the language the students will ask in. For KBTU that
usually means **Russian**. You may mix in English terms where students use them
(`add/drop`, `retake`, `GPA`). The embedding model is multilingual, so this
does not hurt search quality.

**Diversify vocabulary.** If the topic has a common English term AND a Russian
one, include both somewhere in the entry (title, content, or keywords). For
example: `retake / ретейк / пересдача`. This dramatically improves recall
when students phrase the same question differently.

**Don't include "I don't know" fallbacks or meta-text.** The LLM has its own
refusal line. You write only the facts.

### 3.3 `category` (optional but useful)

A short, lowercase slug. Reuse an existing category whenever possible — new
slugs fragment the search space and clutter the admin UI.

Current categories visible in the admin file list. Before creating a new one,
scroll there and pick the closest match.

- ✅ `academic`, `finance`, `dorm`, `schedule`, `documents`, `registrar`
- ❌ `Academic`, `ACADEMIC`, `Академ.`, `академ. вопросы` (case/spacing
  inconsistency — the system normalizes to lowercase but extra variants still
  confuse admins)

### 3.4 `keywords` (optional but powerful)

A comma-separated list of 5–15 short tokens. Goal: cover the words a student
is *likely to type* that may not appear verbatim in the content.

- Include **abbreviations**: `рупы`, `руп`, `RUP`
- Include **transliterations** in both directions: `retake`, `ретейк`, `ретак`
- Include **synonyms** and slang: `общага` for dorm, `кафедра` for department
- Include **typos** if they're common enough to matter
- Do NOT include full sentences — those don't help embedding or the file
  keyword gate

The keywords field has two jobs:

1. It's appended to the embedded string, enriching the vector.
2. It's used by the **file fallback filter** as a case-insensitive substring
   gate. If a keyword does not appear literally in the user query, the file
   will not be attached via the fallback path. (See section 4.4.)

---

## 4. File Entries — Field Reference

Files are more demanding than knowledge entries because **the model cannot see
their contents**. A photo of the KBTU map is just bytes; a PDF of the course
catalog is just bytes. Every signal about what's *inside* must come from the
fields you fill in.

### 4.1 `title` (strongly recommended)

The full human name of the file. Not the file-system filename.

- ✅ `РУП ВТиПО 2024-2025`
- ✅ `Карта корпуса КБТУ`
- ✅ `Add/Drop guide — instructions for SITE students`
- ❌ `document.pdf`
- ❌ `Screenshot 2024-10-12`
- ❌ `#карта` (that's a caption hashtag, not a title)

### 4.2 `caption` (required — this is where you describe the file)

One to three sentences telling the reader what's inside. Pretend the reader
can't open the file. Mention the key terms that appear inside — course codes,
office names, procedure names — because *that* is what the embedding model
will match against.

Good caption for the Add/Drop PDF:

> Техническая инструкция (гайд) по процедуре Add/Drop (адд дроп, регистрация
> на дисциплины) для студентов ШИТиИ (SITE). Руководство по работе с порталом
> WSP (wsp.kbtu.kz). Правила добавления (ADD), удаления (DROP) и замены
> (REPLACE) предметов. Ограничения по времени (дедлайн до 13:00), даты
> регистрации, запрет на замену осенних дисциплин на весенние. Значение
> статусов заявки (Подан/Filed, Одобрено). Контакты деканата и офиса
> регистратора.

This caption is dense with searchable terms (`Add/Drop`, `адд дроп`, `WSP`,
`ADD`, `DROP`, `REPLACE`, `дедлайн`, `статус`, `деканат`) without being
padding.

Bad caption:

> `#карта`  ← a single hashtag tells the embedding nothing

### 4.3 `category`

Same rules as knowledge categories. Use a short lowercase slug. For files,
common slugs are `map`, `rup`, `calendar`, `syllabus`. The category is
auto-detected from a hashtag in the Telegram post
([bot/handlers/files.py:10-14](../bot/handlers/files.py#L10-L14)) but admins
should normalize it afterwards.

### 4.4 `keywords` — **do not skip this field**

For a file to be attached via the vector fallback path, at least one keyword
must appear as a case-insensitive substring of the user's query. This is a
hard gate. A file with no keywords can only be attached via the curated path
(explicit linking to a knowledge entry).

Rules of thumb:

- Include the main nouns that describe the file's purpose. Map file: `карта`,
  `map`, `корпус`, `кбту`. RUP: `руп`, `rup`, `учебный план`, `vtipo`, `вт`.
- Include the programme code if applicable (`vtipo`, `ios`, `fce`).
- Use short tokens. The gate matches substrings, so `учебный план` will match
  the query `рабочий учебный план` but `рабочий учебный план на 2024-2025` would
  NOT match a query like `учебный план`.
- Prefer 5–10 keywords. More is fine. Fewer than 3 is risky.

### 4.5 Curated linking — the primary path

In the knowledge edit form there's a multi-select **"Прикреплённые файлы"**.
Use it. Whenever a knowledge entry has an obviously-related file, link them
explicitly. The bot then attaches that file unconditionally whenever the
knowledge entry is retrieved — no threshold, no keyword gate.

This is the path that makes file attachment reliable. Keywords + vector
fallback is the safety net for questions where the knowledge entry happens
not to match.

---

## 5. Testing an Entry — the Playground

After adding or editing, open **🧠 Лаборатория** in the admin panel and run a
few realistic queries. For each query you'll see:

- The top-3 knowledge matches with their cosine distance. The entry you just
  wrote should appear near the top for queries it is supposed to answer.
- The top-5 file matches with distances, whether each file's keywords hit the
  query, the gap, and the final filter decision (`🎯 Filter selects:` /
  `⛔ Filter rejects all candidates`).

**Do this before you close the form.** Iterate: if a query you expected to
match is missing or ranked low, add a keyword or rephrase a sentence in the
content, save, and try again.

---

## 6. Anti-Patterns

| Anti-pattern | Why it hurts | Fix |
|---|---|---|
| One-word caption (`#карта`) | Embedding has no vocabulary to match against | Write a real caption |
| Title = filename (`document.pdf`) | Same as above; the filename is usually gibberish | Use the human name |
| Content stuffed with keywords, no sentences | E5 expects natural text; keyword dumps embed poorly | Put keywords in the `keywords` field and write prose in `content` |
| Content that says "see the file" | The LLM cannot open files — it will have nothing to say | Inline the answer in `content` AND attach the file |
| Creating a new category for every entry | Fragments the category space | Reuse existing slugs |
| Russian-only content for a term used in English (`retake`) | Students who type `retake` get no match | Add the English term to `keywords` or `content` |
| Copy-pasting the same entry with minor edits | Two near-identical vectors compete and split top-K ranking | Merge into one complete entry |
| Editing a file without re-saving from the admin form | The embedding is not regenerated, metadata goes stale | Always save through the admin form — it re-embeds automatically |

---

## 7. Worked Examples

### 7.1 Good knowledge entry

```
Title:    Процедура Add/Drop (замена дисциплин)
Category: academic
Keywords: add/drop, add drop, адд дроп, замена дисциплин, drop, replace,
          wsp, регистрация на предметы, первая неделя семестра
Content:
Add/Drop — это первая неделя семестра, в течение которой студент может
добавить (ADD), удалить (DROP) или заменить (REPLACE) дисциплину в своём
расписании через портал WSP (wsp.kbtu.kz).

Как подать заявку:
1. Зайдите в WSP → раздел Academic → Add/Drop request.
2. Выберите действие (ADD / DROP / REPLACE) и дисциплину.
3. Подтвердите заявку — статус изменится на "Подан" (Filed).
4. Дождитесь одобрения офиса регистратора — статус станет "Одобрено".

Ограничения:
- Дедлайн: пятница первой недели семестра до 13:00.
- Осенние дисциплины нельзя заменять на весенние.
- После дедлайна изменения возможны только через апелляцию в деканат.

Контакты: офис регистратора, корпус C, каб. 114, registrar@kbtu.kz.
```

Why it works:
- Title is a phrase a student might type.
- Content covers what / how / when / where / who to contact.
- Keywords include English, Russian, transliteration, and synonyms.
- Category is a reused slug.

### 7.2 Good file entry

```
Title:    Add/Drop guide — SITE students
Category: academic
Keywords: add/drop, add drop, адд дроп, замена дисциплин, wsp, site,
          регистрация, дедлайн, drop, replace
Caption:
Техническая инструкция (гайд) по процедуре Add/Drop для студентов ШИТиИ
(SITE). Пошаговое руководство по работе с порталом WSP (wsp.kbtu.kz),
правила добавления (ADD), удаления (DROP) и замены (REPLACE) дисциплин.
Дедлайны, статусы заявки (Подан/Filed, Одобрено), ограничения на замену
осенних дисциплин на весенние, контакты деканата ШИТиИ и офиса регистратора.

Linked to knowledge entry: "Процедура Add/Drop (замена дисциплин)"
```

Why it works:
- Caption describes *contents*, not just "it's a guide".
- Keywords cover multiple phrasings.
- Linked to the relevant knowledge entry, so it attaches whenever that
  entry is retrieved — no dependence on the vector fallback.

### 7.3 Bad entry — before and after

**Before:**

```
Title:    (empty)
Category: info
Keywords: (empty)
Content:  Ретейк 35000.
```

Problems: no title, vague category, no keywords, content too terse for the
LLM to produce a useful answer.

**After:**

```
Title:    Стоимость и процедура пересдачи (Retake)
Category: finance
Keywords: ретейк, retake, ретак, пересдача, цена, стоимость, оплата
Content:
Пересдача одного курса (retake) стоит 35 000 ₸. Оплата производится через
Kaspi по реквизитам КБТУ до подачи заявки на пересдачу. Подать заявку
можно через офис регистратора (корпус C, каб. 114) в течение первых двух
недель следующего семестра. Необходимые документы: копия квитанции об
оплате, заявление на имя регистратора.
```

---

## 8. Troubleshooting

**"My entry doesn't match queries I expect it to match."**
Open the playground. If the distance is `> 0.35` on a reasonable query, your
embedding is weak. Common causes: content is too short, vocabulary doesn't
overlap with typical queries, missing keywords. Rewrite the content to include
the terms students actually use.

**"My file is not being attached even though it's clearly relevant."**
Three things to check in the playground:
1. Is the file's top distance ≤ 0.20? If not, strengthen the caption/title/
   keywords.
2. Does at least one keyword literally appear in the test query?
3. Is there a noise file ranked close behind (gap < 0.05)? If yes, you can
   either (a) add a more distinctive keyword to the winning file, or (b) add
   keywords to the noise file so the gap comparison happens between two
   keyword-matching files.
If none of that works, use the **curated link** — attach the file to the
relevant knowledge entry. That bypasses the vector fallback entirely.

**"The bot gives an answer but misses a detail that's in my content."**
The LLM has a 1024-token answer limit and is instructed to stick to the
context. If the context is very long, the model may compress. Split a single
huge entry into 2–3 focused entries (e.g., separate "eligibility" from
"procedure" from "fees").

**"The bot refuses to answer but my entry exists."**
Distance > 0.35 — the retrieval filter rejected it. Improve the title,
content, and keywords so the vector lands closer to the query. Re-test in the
playground.

---

## 9. Checklist Before You Save

For every **knowledge** entry:

- [ ] Title is 2–8 words and distinctive
- [ ] Content is a complete answer covering who/what/where/when/how/how much/contact
- [ ] Content is written in the language students will use (usually Russian)
- [ ] Alternative terms (English + Russian + abbreviations) appear somewhere
- [ ] Category is a reused lowercase slug
- [ ] Keywords field has 5–15 short tokens
- [ ] Any relevant file is linked via the multi-select
- [ ] Tested in the playground with 2–3 realistic queries

For every **file** entry:

- [ ] Title is a human-readable name (not the filename)
- [ ] Caption describes *what's inside* in 1–3 sentences with concrete terms
- [ ] Category is a reused lowercase slug
- [ ] Keywords has at least 5 tokens, including short nouns a user would type
- [ ] Linked to at least one knowledge entry (if possible) — this is the
      reliable path
- [ ] Tested in the playground with the expected query; the filter decision
      is `🎯 Filter selects`

---

## 10. Field Summary Table

| Field | Knowledge | Files | Max length | Format |
|---|---|---|---|---|
| `title` | strong signal, 2–8 words | human name of the file | 255 | Plain text |
| `content` / `caption` | full self-contained answer | description of file contents | unlimited | Prose, numbered lists allowed |
| `category` | reused lowercase slug | reused lowercase slug | ~50 | `academic`, `finance`, `map`, ... |
| `keywords` | 5–15 tokens, synonyms+translits | **required for fallback**, 5–10 tokens | array | Comma-separated in the form |

---

*Last review: 2026-04. When the embedding model or search thresholds change,
update section 1 and section 4.4 accordingly.*
