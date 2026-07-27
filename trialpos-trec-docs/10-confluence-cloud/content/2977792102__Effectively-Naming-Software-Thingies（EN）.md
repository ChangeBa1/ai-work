---
confluence_id: 2977792102
title: "Effectively Naming Software Thingies（EN）"
parent_id: 2977792153
version: 2
version_at: 2024-10-08T23:36:08.962Z
status: current
source_url: https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/2977792102
synced_at: 2026-07-07
---

# Effectively Naming Software Thingies（EN）

# Effectively Naming Software Thingies

Naming stuff is a key part of our programming life. A great deal of books and articles were written about how important that is and how to do it well. Here is my summary of key points and guidelines I’ve gathered.

# Why Naming is Important?

> _“As code authors we want our code as easy as possible to understand, quick skim, not an intense study. Not like an academic article where it’s your job to dig the meaning out of the paper.” — paraphrased from Clean Code._

Most of our coding time we read existing code. Therefore it should be as readable and clear as possible by us humans. This happens by selecting words and building sentences with our code that are close as possible to the human language that we naturally use. Naming is a key part of that.

Moreover, coming up with a good name reveals the nature of a thing, which helps us divide the responsibilities of our components better. This ultimately leads to maintainable and extendable code.

Because naming things is one of the most common tasks that we do, we better do it well and as naturally as possible.

# Why Naming is Hard?

Naming is an art form that requires good descriptive skills. It comes naturally for some, but most of us struggle with it.

Another reason is that we fear that the team won’t like our choice. Because of it we even fear to change a poorly chosen name. We take these rejections as personal rejections. What happens is that we leave these bad names to rot and slide into other parts of our code and contaminate them with their obscurities and carelessness.

# How to Start?

You may feel the need to skim through the bullet lists as quickly as possible. I think it’s a good way to start. But after a brief overview, I urge you to take it bit by bit, don’t overwhelm yourself. Practice the [Kaizen](https://en.wikipedia.org/wiki/Kaizen) method, and take a small step at time. Challenge yourself to follow a couple of these guidelines every few days, and review yourself if you’ve succeeded.

On your first go, try to follow the guidelines in the next section. They are applicable in almost any situation. I’ve tried to summarize them as much as possible.

Don’t be afraid to refactor and rename stuff. Practice makes… you know… better names. The “worst” that could happen is that it will get changed again later. Either way, you will learn and get better.

# Don’t Make Me Think — Meaningful Names

Don’t make me think! This is probably the **most important guideline**. Names should not make us raise questions about the meaning of objects and values. Coding is hard enough, without trying to understand the meaning behind a weird function name or remember the contents of some list.  
For a more detailed discussion, please look at Robert Martin’s _“Clean Code”._

* **Select Intent Revealing Names.** Code as explicit as possible. If the variable stores the last updated record, name it `lastUpdatedRecord`, not just `record`, or even `lastRecord` (The last record in a file??).
* **Make Meaningful distinctions.** Don’t distinguish between similar names by misspelling or suffixing with numbers and noise words, just to satisfy the compiler. This is Non-informative. For example, `ProductInfo` vs `ProductData` What kind of info the `ProductInfo` has that the `ProductData` doesn't.
* **Add meaningful context .** The scope of the thing you are naming should add meaningful context. The variable state is not meaningful in itself. Put it in a well named class, e.g. `address.state` or `engine.state`, and others will automatically understand your intention.  
  The least favorable but sometimes appropriate way to add context is to prefix or suffix the name of the variable - `addressState`.  
  Every part of the call chain should add only new context. This way you can shorten your names and keep them meaningful enough.
* **Use Solution Domain Names**. Your code will be read by programmers, then you can and should use computer science terms (`jobQueue`), pattern names (`AccountVisitor`), algorithm names, math terms, and so on.
* **Use Problem Domain Names.** If the thing is more related to the problem domain, then it probably has an appropriate name in the domain. It will help you to familiarize more with the domain and have a common language with the clients. It has the added benefit of decoupling the domain concepts from the specific solution. You could use a \`string address\` and mean that this is the shipping address. But it will be clearer and more robust to just use \`Address shippingAddress\`.

```
// instead of
String state;
String streetAddress;
Int houseNumber;// use
Address address
```

* **Don’t Abbreviate.** Say `getWindow` not `getWin`.

# Concepts

Naming objects is about abstracting and encapsulating behavior within a concept.

* **Pick One Word per** **Abstract** **Concept** and stick with it. Soon enough you and your team will have a common language and will know what to expect from certain names. What’s the difference between `fetch` and `retrieve`? pick and use only one.
* However, **Don’t Pun** and use the same word for different things. Suppose you have two classes. One class will create and add a new user object using an `add()` method. The second class has a method that inserts a parameter into a collection. The “One Word per Concept” rule can mislead you to name the two methods `add()`, when they actually have different semantics.  
  Another example for a name being used for different purposes is the God-Variable `temp, tmp, tmp1 ...`.
* **Avoid Mental Mapping**. This is _VERY_ important! Don’t make your readers mentally translate names to something else they know. You should even name loop counters to make it simpler. Don’t be a _Smart Programmer_ who shows off his mental juggling abilities. Be a _Professional Programmer_ that understands that _**Clarity is King**._
* **Use Conventions for Common Operations.** For example, how should I get the Id here?

```
worker.getId() 
candidate.id()
employee.id.get()
supervisor()
```

* **Use opposites precisely**. If you can `open()`, you should be able to `close()`; After you `start()` you should `stop()`

# Noise and Boilerplate

The name should be as clean and **short** as possible. Noise makes the reader read more without any added benefit except confusion.

* **Don’t Make Noise.** What do you mean by `ProductInfo`? How is it different from `ProductData`? Suffixes like that are just noise. Compiler candy. They don’t add distinct meaning. Some noise prefixes like 'the', 'a'/'an', 'all' can be used to make a meaningful distinction, in which case they are not considered as noise.
* **Avoid Comments.** A good name is a thousand times better than a comment.
* **Leave Legacy Practices Behind**. Don’t be a cave person, instead use a modern IDE with color coding, docs and reference finding tools.  
  Say no to [Hungarian notation](https://en.wikipedia.org/wiki/Hungarian_notation). The type in the name will lead to misinformation in the next refactor and quick type change.  
  Some will argue to not _prefix members_ with ‘m\_’ or just ‘\_’. Personally I like ‘\_’ with the added distinction from regular variables and parameters, for the low price of one character. We don’t have to agree on everything…
* **Beware of ‘I’ for Interface Trap.** This may help and be the convention in some platforms. Just don’t slap an ‘I’ in front of a concrete class to get an interface. `IDollar` is not a better name than Currency. [Carlo Pescio](http://www.carlopescio.com/2011/04/your-coding-conventions-are-hurting-you.html) elaborates on that point and on the point of OOP vs Procedural.
* **Don’t Add Gratuitous Context** — For example, don’t use abbreviated project name as prefix e.g. `GSDMailingAddress`. This works against your IDE (what happens to auto-completion when you start searching for a method named `getSomethingImportant()`?) and unusable in another project.

# Disinformation

Sometimes caused intentionally from the start, and sometimes during normal life-cycle of development and refactoring. Either way…

* **Avoid Related Words** and abbreviations that are too related to other meanings than the one we meant  
  Avoid Using Type in the Name, e.g. `accountList`. someday someone will change the type to `hashSet`, and the name will lose its meaning.
* **Avoid Small Differences** between long names, for example, using o or l as variable names, they are too similar to 0 and I.
* **Avoid Comments. Again.** code changes, and nobody updates the comments.

# Human Reader

> _“Programs are meant to be read by humans and only incidentally for computers to execute” — Donald Knuth_

* The **Length of the Name** should be as long as necessary to convey the meaning accurately, however it should be as short as possible to increase readability.
* **Favor Readability** over brevity — `CanScrollHorizontally` is better than `ScrollableX`.
* Make the code readable like **Paragraphs and Sentences** and use grammar as correctly as possible.
* **Pronounceable Names** — you must be able to discuss about it without sounding like an idiot. e.g. `plhmbuster`.
* **Don’t be Cute or Clever** — funny names remain understandable only as long as you and the people who share the joke stay on the project.
* **Avoid Encoding and Emoji’s.** (I should not even mention this)
* **Use Searchable Names** in order to help the IDE help you, for example, use constants for magic string and numbers.
* **Avoid Similar Sounding Names.**
* **Avoid Easily Misspelled Names.**

# Conclusion

Good names help make better code. When we build large systems, most of the time we read. And we all enjoy a well written story. Make your code read like a story.

Did I miss something? Do you want to let me know what you think? Please, do…

‌

[https://medium.com/@rabinovichsagi/effectively-naming-software-thingies-fcea9d78a699](https://medium.com/@rabinovichsagi/effectively-naming-software-thingies-fcea9d78a699)

by Sagi Rabinovich@Medium
