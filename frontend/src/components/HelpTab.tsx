/**
 * Help: everything the check screen used to say, and the questions it never
 * answered (NFR-4, US-28).
 *
 * The author, on the released build: "this has way too many words on the screen.
 * create a help me tab and put all of the text you are removing plus some FAQs
 * on that tab."
 *
 * **This is a reading page, and the check screen is a working page.** That is
 * the whole of the split. Every sentence removed from the check screen was true
 * and was added for a reason, and none of them was worth reading in the middle
 * of somebody's work; here they are worth reading, because a person on this tab
 * came to read. So the copy is not pasted across, it is rewritten for a reader:
 * headings they can scan, answers to questions rather than caveats attached to
 * controls, and no requirement identifiers anywhere on the page.
 *
 * There are no controls on it except links. Nothing here changes anything, and
 * a page of explanation with a button on it invites an agent to think they have
 * left something undone.
 *
 * **What did not move here.** The prototype banner above the masthead, the
 * footer, and the FR-9 error messages. Cutting words is not licence to drop a
 * message that names a real problem: an agent whose file could not be read has
 * to be told so where they are, and the banner is the standing statement of
 * what this tool is and is not. Those stay exactly where they were.
 *
 * Headings are `<h3>` under the panel's own `<h2>`, so the tab's outline is
 * one level deep and a screen reader's heading list reads as a list of
 * questions rather than as a flat run of siblings.
 */

/**
 * One question and its answer.
 *
 * The question is the heading, in the words an agent would use rather than in
 * the words the requirements use. "Why is the brand name found but not judged
 * for type size" is what someone actually wonders; "OOS-5" is what the
 * traceability matrix calls it, and it is not on this page.
 */
function Entry({ question, children }: { question: string; children: React.ReactNode }) {
  return (
    <div className="help__entry">
      <h3 className="help__question">{question}</h3>
      {children}
    </div>
  )
}

export function HelpTab() {
  return (
    <div className="help" aria-labelledby="help-heading">
      <h2 id="help-heading">Help</h2>
      <p className="help__lead">
        What this tool checks, what its answers mean, and what happens to the files you give it.
      </p>

      <section aria-labelledby="help-uploading">
        <h3 className="help__section" id="help-uploading">
          Uploading
        </h3>

        <Entry question="What do I upload?">
          <p>
            One place takes everything: PDFs and images, one file or several. You do not have to
            sort them first.
          </p>
          <p>
            We work out what each one is from the file itself. An application tells us what the
            label should say. An image of the label shows us what it does say.
          </p>
          <p>
            What each file was taken to be is shown beside it, so if we get one wrong you can see it
            rather than having to guess.
          </p>
        </Entry>

        <Entry question="What if I only have the application, or only a photo?">
          <p>Either one on its own is a valid submission, and both work differently.</p>
          <p>
            An application usually carries its own label artwork, affixed by the applicant. When it
            does, that artwork is the label we check, and you do not have to add an image.
          </p>
          <p>
            A photo on its own gives us the label and nothing to compare it against, so we check
            what the label carries on its own: the government warning, and whether the alcohol
            content and net contents are printed on it. Type the application values in if you have
            them and you get the full comparison.
          </p>
        </Entry>

        <Entry question="Where does beverage type come from?">
          <p>
            Item 5 of the application, which is three check boxes: distilled spirits, wine, or malt
            beverage. We look at the boxes on the page and report the one that is filled in, when
            one of them clearly is.
          </p>
          <p>
            It is never compared against the label. A label does not print "distilled spirits" as a
            form answer. What it does is decide which numeric rule we run: the proof cross-check for
            spirits, range handling for wine.
          </p>
          <p>
            If the boxes were too close to separate, or none was filled in, the field is left for
            you to choose.
          </p>
        </Entry>
      </section>

      <section aria-labelledby="help-results">
        <h3 className="help__section" id="help-results">
          Reading the results
        </h3>

        <Entry question="What do the outcomes mean?">
          <dl className="help__outcomes">
            <dt>Match</dt>
            <dd>
              The application declared a value and we found it on the label. Two things agreed.
            </dd>

            <dt>Contains</dt>
            <dd>
              The label carries something the regulation requires it to carry, and the application
              declared nothing to compare it against. One thing was found, and it is the thing that
              had to be there. This is a pass.
            </dd>

            <dt>Needs human review</dt>
            <dd>
              The two values are close but not the same, or the label says something that
              contradicts itself. This is the one to look at.
            </dd>

            <dt>Does not match</dt>
            <dd>
              The application declared a value and the label does not carry it, or the label is
              missing something the regulation requires.
            </dd>

            <dt>Not found</dt>
            <dd>
              We could not read this on the label at all. That may be the photo rather than the
              label; a clearer image often fixes it.
            </dd>

            <dt>Not compared</dt>
            <dd>Neither the application nor the label gave us anything to work with.</dd>

            <dt>Read from the artwork</dt>
            <dd>See the next question.</dd>
          </dl>
        </Entry>

        <Entry question="Why does it sometimes say a value came from the label artwork inside the application?">
          <p>
            Because on that row, both things we were comparing came out of the same picture. The
            applicant did not type the value into a box on the form; it is printed on the artwork
            they attached, and that same artwork is what we are checking.
          </p>
          <p>
            Comparing a picture against itself always agrees, so a green tick there would mean
            nothing. We say where the value came from instead.
          </p>
          <p>
            To turn that row into a real check, add a photo of the bottle, or type the value in from
            the filing.
          </p>
        </Entry>

        <Entry question="Why is the brand name found but not judged for type size or placement?">
          <p>
            Finding the brand name on the label shows that the text is there. It does not show that
            it is there as the brand, in the type size the regulation requires, or on the panel it
            belongs on.
          </p>
          <p>
            Type size, characters per inch and required panels are not checked by this tool at all.
            They are yours to judge.
          </p>
        </Entry>

        <Entry question="Why can it not read a photo of a bottle as well as it reads a filed label?">
          <p>
            A label wrapped on a round bottle is curved, and the text at the edges is stretched and
            turned away from the camera. Glare, shadow and a shallow angle all make it worse.
          </p>
          <p>
            Filed artwork is flat, printed at full resolution, and lit evenly, which is why it reads
            well. Three photos of the same bottle can still leave the brand unreadable on curved
            glass.
          </p>
          <p>
            You can send up to three photos of one label and we read each one and merge what they
            show, which is the front-and-back case. It is a workaround for the curve rather than a
            solution to it.
          </p>
        </Entry>
      </section>

      <section aria-labelledby="help-about">
        <h3 className="help__section" id="help-about">
          About this tool
        </h3>

        <Entry question="What happens to my files?">
          <p>Nothing is stored.</p>
          <p>
            Your files are read on this server and thrown away when the answer comes back. They are
            not written to disk, not put in a log, not kept for a later request, and not sent to TTB
            or anywhere else.
          </p>
          <p>
            The results live in this page until you leave it or clear it. There is no account, no
            history and nothing to come back to.
          </p>
        </Entry>

        <Entry question="What is this tool not?">
          <p>
            It is not an official TTB or Treasury system. It is a prototype, built by Kimberly D.
            Kight as a take-home assignment.
          </p>
          <p>
            It recommends and you decide. Every answer it gives is a starting point for your
            judgement, not a verdict, which is why it shows you what it read and where it found it
            rather than only a result.
          </p>
          <p>
            It does not check bold type on the government warning, type size, characters per inch,
            or required panels; it does not talk to the COLA system; and it has never been run
            against a real filed application.
          </p>
        </Entry>
      </section>
    </div>
  )
}
