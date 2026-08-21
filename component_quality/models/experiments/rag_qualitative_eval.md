# RAG Qualitative Evaluation

This report samples 30 historical proposal chunks and queries the RAG system to retrieve the top-5 most similar historical feedbacks.
> Note: Quantitative Recall@K cannot be computed as there is no isolated hold-out query set with known relevance judgments. Manual categorization is required.

## Query 1
**Student Proposal Chunk:**
> I...

**Retrieved Feedback:**
**1. [Sim: 1.000]** Avoid first person.
**2. [Sim: 1.000]** Avoid first person
**3. [Sim: 0.664]** should be '
**4. [Sim: 0.610]** Should be indirect (e.g. this thesis).
**5. [Sim: 0.610]** Avoid "we"

---
## Query 2
**Student Proposal Chunk:**
> We will discussthe landscape of adapting current AI-enhanced data analysis to the importance of TME, address the limitationsof current AI models in incorporating TME data and explore the anticipated improvement of personalizedtreatment prediction. By leveraging advanced AI techniques to model the heterogeneity of TME, this researchaims to generate valuable insights that are both biologically meaningful and clinically useful, paving the wayfor more comprehensive and effective cancer therapies...

**Retrieved Feedback:**
**1. [Sim: 0.636]** If so, were are the sources here? If AI has emerged you should be able to mention them
**2. [Sim: 0.630]** If you ask questions, you should answer them. Not only Research questions needs to be answered
**3. [Sim: 0.629]** Very good and clear presentation of current limitations
**4. [Sim: 0.626]** Makes sense to me
**5. [Sim: 0.620]** Good

---
## Query 3
**Student Proposal Chunk:**
> Motivation and Approach sections as 1.5pages eac...

**Retrieved Feedback:**
**1. [Sim: 0.485]** Motivation part overall well structured.
**2. [Sim: 0.461]** I don't get this
**3. [Sim: 0.448]** The motivation should propose defining and achievable research questions (RQs). You are not very clear about that. The two blue sections from the bottom might be proposing something like research questions. If that is the case, then I find them too imprecise for a thesis.
**4. [Sim: 0.448]** This reads more like a sales-pitch than a Motivation for a scientific research.
**5. [Sim: 0.448]** Very good section all in all!

---
## Query 4
**Student Proposal Chunk:**
> sychology researchers or healthcareinstitutions...

**Retrieved Feedback:**
**1. [Sim: 0.519]** Good limitation, but what is the reasoning behind it? Ideally, try to justify as many decisions as possible in an expose
**2. [Sim: 0.518]** If you cite related work (which is good), include it in a smoother way. You want to tell a story around them, not just name them
**3. [Sim: 0.512]** Terminology, before deciding physician
**4. [Sim: 0.511]** Methodology should describe and convince, how the research questions are to be answered. You list several methods, but do not explain their purpose.
**5. [Sim: 0.505]** In my opinion, this should already be kind of clear now whether it is highly researched or not- otherwise you cannot do your research right?

---
## Query 5
**Student Proposal Chunk:**
> Generative AI...

**Retrieved Feedback:**
**1. [Sim: 1.000]** SOTA.
**2. [Sim: 1.000]** You should explain what you mean with "Generative AI" since this is such a broad term
**3. [Sim: 0.870]** What is "the generative artificial intelligence"? If you call it "the", do you refer to something specific?
**4. [Sim: 0.836]** Grammar: is ready
**5. [Sim: 0.788]** Which are?

---
## Query 6
**Student Proposal Chunk:**
> [1]...

**Retrieved Feedback:**
**1. [Sim: 1.000]** this should come before the '.'
**2. [Sim: 0.947]** See above
**3. [Sim: 0.863]** For better readability, name the title of the source using \citetitle.
**4. [Sim: 0.863]** what's this citation for?
**5. [Sim: 0.863]** before '.'

---
## Query 7
**Student Proposal Chunk:**
> When considering which technology to choose, the perceived capabilities may also depend on the type ofproblem that is to be solved....

**Retrieved Feedback:**
**1. [Sim: 0.592]** Use references here
**2. [Sim: 0.557]** Theoretical framework.
**3. [Sim: 0.538]** It seems that this topic involves some sociology concepts/knowledge that would be really helpful if elaborated on here. For example, I do not understand what is meant by "competence of gendered technology". Perhaps it can be worded better if you meant this instead: "In the research, variables related to how technology is represented through a specific gender affects its perception and competence"
**4. [Sim: 0.482]** add statistic
**5. [Sim: 0.480]** This is not aligned with the RQ proposed in the motivation part.

---
## Query 8
**Student Proposal Chunk:**
> study explores its application in a novel context...

**Retrieved Feedback:**
**1. [Sim: 0.514]** Repetition.
**2. [Sim: 0.506]** study
**3. [Sim: 0.502]** Typo: Research
**4. [Sim: 0.499]** Motivation part overall well structured.
**5. [Sim: 0.493]** If you cite related work (which is good), include it in a smoother way. You want to tell a story around them, not just name them

---
## Query 9
**Student Proposal Chunk:**
> according to a survey...

**Retrieved Feedback:**
**1. [Sim: 0.600]** For what?
**2. [Sim: 0.566]** Anchor.
**3. [Sim: 0.548]** Conducting another survey without declaring use and process is not useful. Cut it out or state its use.
**4. [Sim: 0.500]** This ideally goes into the research question or subquestions, because you are narrowing down the problem like this (which is good)
**5. [Sim: 0.493]** A transition to the research questions would be better.

---
## Query 10
**Student Proposal Chunk:**
> present information based on their interest...

**Retrieved Feedback:**
**1. [Sim: 0.462]** Detecting a threat to validity and preventing it.
**2. [Sim: 0.446]** cite!
**3. [Sim: 0.435]** grammar :)
**4. [Sim: 0.427]** Teaser.
**5. [Sim: 0.424]** Motivation part overall well structured.

---
## Query 11
**Student Proposal Chunk:**
> ombing o...

**Retrieved Feedback:**
**1. [Sim: 0.560]** o should be small
**2. [Sim: 0.548]** use
**3. [Sim: 0.476]** help of*
**4. [Sim: 0.453]** not formal - better use "although"
**5. [Sim: 0.373]** Wrong Grammar: in addition

---
## Query 12
**Student Proposal Chunk:**
> user focused...

**Retrieved Feedback:**
**1. [Sim: 0.536]** Formulation. Participants would fit better in a scientific context.
**2. [Sim: 0.514]** too generic
**3. [Sim: 0.500]** how do you want to measure such a thing?
**4. [Sim: 0.481]** Not clear how this is being measured with the given metrics
**5. [Sim: 0.440]** to be a ... *

---
## Query 13
**Student Proposal Chunk:**
> "cost of healthcare willlikely rise over the years" [6] as the "healthcare is highly labor-intensive" [6] and increasing patient loads...

**Retrieved Feedback:**
**1. [Sim: 0.506]** Weird sentence construction
**2. [Sim: 0.506]** This sentence is really hard to read. The flow is really off
**3. [Sim: 0.494]** cite a source to this growth
**4. [Sim: 0.489]** Outside of healthcare, is it okay? Be precise with your wording. This sounds like it's just for healthcare important
**5. [Sim: 0.482]** Hook.

---
## Query 14
**Student Proposal Chunk:**
> Theoretical Framework...

**Retrieved Feedback:**
**1. [Sim: 1.000]** Theoretical Framework.
**2. [Sim: 1.000]** well once again, it's not a good idea you put subtitle one directly next one. Write some text to make the essay fluent and coherent, it's not a workshop slide
**3. [Sim: 1.000]** Missing explanation of LLMs, Bias and hallucination
**4. [Sim: 1.000]** Lack of illustration of how the proposed theoretical framework is connected to the Holographic AI assistants and the method will be designed in this project.
**5. [Sim: 1.000]** You could be more precise and better highlight your work's connections and usage.

---
## Query 15
**Student Proposal Chunk:**
> AR...

**Retrieved Feedback:**
**1. [Sim: 0.827]** AR != Holography. Which one are you actually investigating?
**2. [Sim: 0.809]** Terminology. Abbreviations must always be introduced first.
**3. [Sim: 0.594]** This term would benefit from a brief definition.
**4. [Sim: 0.482]** also seems very general to me - what is the theoretical idea/foundation behind this RQ?
**5. [Sim: 0.459]** Terminology.

---
## Query 16
**Student Proposal Chunk:**
> This...

**Retrieved Feedback:**
**1. [Sim: 1.000]** these
**2. [Sim: 1.000]** never use vague pronoun in research question, reformulate your RQ 2 please
**3. [Sim: 0.654]** Grammar: This
**4. [Sim: 0.591]** Formulation.
**5. [Sim: 0.589]** Formulation.

---
## Query 17
**Student Proposal Chunk:**
> examles...

**Retrieved Feedback:**
**1. [Sim: 0.558]** how?
**2. [Sim: 0.492]** research*
**3. [Sim: 0.459]** ... to the end of the pararaph, anker present
**4. [Sim: 0.457]** Repetition.
**5. [Sim: 0.450]** "study" is not personal, you'd better use "concerns of the study"

---
## Query 18
**Student Proposal Chunk:**
> Large-language models (LLMs) have the potential to be interactive companion and create truly personalizedlearning paths for students. The model could take into account the past performance, existing knowledge,and personal preferences of the student to create tailored curriculum for them. It could generate learningmaterials and adapt them based on how good the student is handling. It could also serve as an always-onlinehigh-quality teacher which is available to every student....

**Retrieved Feedback:**
**1. [Sim: 0.838]** Overall good initial scope of the research question and its sub-questions
**2. [Sim: 0.789]** This opening provides a strong context for the SOTA section, emphasizing the growing relevance of the topic. It effectively captures attention and sets the stage for the discussion.
**3. [Sim: 0.766]** It effectively focuses on practical applications while also addressing personalization, which is crucial in educational technology. It provides a clear direction for research without being overly broad.
**4. [Sim: 0.757]** Good research questions
**5. [Sim: 0.739]** A RQ should not be a yes/no question. Apart from that, it is a really broad scope and not clearly explained what you mean with "scalable, culturally relevant and linguistically accurate"

---
## Query 19
**Student Proposal Chunk:**
> This will involve processing sample medical data through generative AI models to assess their performancein different specialtie...

**Retrieved Feedback:**
**1. [Sim: 0.689]** This does not answer RQ1.2 though? Do you not want to evaluate/compare models against physicians?
**2. [Sim: 0.684]** Theoretical Framework.
**3. [Sim: 0.679]** Dont you think this has been researched already?
**4. [Sim: 0.660]** there is a verb missing here
**5. [Sim: 0.645]** donot know how the privacy is solved here

---
## Query 20
**Student Proposal Chunk:**
> <Example?>...

**Retrieved Feedback:**
**1. [Sim: 1.000]** Placeholder
**2. [Sim: 0.679]** You did not write a schedule yourself
**3. [Sim: 0.515]** Placeholder
**4. [Sim: 0.515]** Where is the Link?
**5. [Sim: 0.424]** Good example.

---
## Query 21
**Student Proposal Chunk:**
> claimed...

**Retrieved Feedback:**
**1. [Sim: 0.586]** provide
**2. [Sim: 0.493]** available?
**3. [Sim: 0.466]** General form: justified text.
**4. [Sim: 0.466]** Create different sections for SOTA, Theoretical Framework and Methodology and put these information under them. Too many repeating phrases and sentences (LLM, LLM-based, LLMs, personalized learning paths...)
**5. [Sim: 0.466]** Good integration of sources.

---
## Query 22
**Student Proposal Chunk:**
> After that Iwant to conduct interviews to get an impression of the students how the experience felt. With this interviewdata and the prompt log of the students I will analyse this and try to answer my research questions....

**Retrieved Feedback:**
**1. [Sim: 0.650]** Good
**2. [Sim: 0.602]** This is a promising strategy. It would be beneficial to provide examples of the kind of teachers or institutions targeted for interviews. Additionally, elaborating on how the insights from these interviews will directly shape the research outcomes could enhance the clarity of this section.
**3. [Sim: 0.579]** Interviewing only teachers who already use LLMs may introduce selection bias. This may limit the generalizability of the findings to broader educational contexts, particularly for teachers unfamiliar or uncomfortable with such technologies.
**4. [Sim: 0.562]** That again is very ambitious.
**5. [Sim: 0.540]** Unless you only want to have 2-3 interviews, one week is definetly not enough

---
## Query 23
**Student Proposal Chunk:**
> Than...

**Retrieved Feedback:**
**1. [Sim: 0.572]** why "or"?
**2. [Sim: 0.497]** phrase: not only something but also something
**3. [Sim: 0.496]** should be '
**4. [Sim: 0.484]** not needed, since the list does not have other elements
**5. [Sim: 0.484]** not needed, since the list does not have other elements

---
## Query 24
**Student Proposal Chunk:**
> one single "one-size-fits-all...

**Retrieved Feedback:**
**1. [Sim: 0.402]** Formulation.
**2. [Sim: 0.396]** word choice, streamline its later with AI tools
**3. [Sim: 0.379]** No space.
**4. [Sim: 0.370]** Hook
**5. [Sim: 0.369]** meaningful & recognizable benefit

---
## Query 25
**Student Proposal Chunk:**
> hurdles...

**Retrieved Feedback:**
**1. [Sim: 0.669]** This section could also deal with the own work. What gap does your work fill?
**2. [Sim: 0.382]** The SOTA is incomplete. The problem is not really clear here. What exactly are the weak points?
**3. [Sim: 0.380]** Very good! It is always important to also consider possible challenges.
**4. [Sim: 0.376]** More information about participants are needed.
**5. [Sim: 0.376]** How are the participants recruited? You could go into more detail about how you want to reach the diverse group.

---
## Query 26
**Student Proposal Chunk:**
> Limited Integration of AI with Holographic Visualization:...

**Retrieved Feedback:**
**1. [Sim: 0.995]** You use a lot of individual paragraphs in your text. However, academic works should be more of a continuous text. Try replacing the individual paragraphs with transitions.
**2. [Sim: 0.810]** The Subtitle doesn't tell us much about the content of the paper. The Title is really captivating and would work really well with a stronger subtitle, that indicates the direction of the paper.
**3. [Sim: 0.810]** That is just the default title - you should come up with your own title (and subtitle)
**4. [Sim: 0.810]** The used title is the same title as the topic. This implicates points deduction
**5. [Sim: 0.793]** Too long

---
## Query 27
**Student Proposal Chunk:**
> their latest model, which is freely available and also suited for manual fine-tuning...

**Retrieved Feedback:**
**1. [Sim: 0.637]** It seems to be a good choice to use LLaMA-3.1. But why wouldn't you use another model. What are LLaMA-3.1's advantages compared to current competitors?
**2. [Sim: 0.631]** What models?
**3. [Sim: 0.509]** You dedicated a lot of time for fine-tuning and evaluation, which is often a iterative process and can take a lot of time
**4. [Sim: 0.491]** training time/cost
**5. [Sim: 0.441]** This part may be broken down into smaller milestones with clear goals

---
## Query 28
**Student Proposal Chunk:**
> There are several cases where diagnostic errors in healthcare, such as pneumonia, cancer, heart failure, whichled to death and disabilities....

**Retrieved Feedback:**
**1. [Sim: 0.939]** 1. Where are the references to these erros? What facts is this sentence based on? 2. The grammar is off in this sentence
**2. [Sim: 0.516]** Good
**3. [Sim: 0.492]** How does cross-validation work with overreliance on AI?
**4. [Sim: 0.492]** This claim is not supported by any source.
**5. [Sim: 0.489]** Very good.

---
## Query 29
**Student Proposal Chunk:**
> unique needs...

**Retrieved Feedback:**
**1. [Sim: 0.416]** Fits well into the topic, but you should explain it better and clarify why its relevant and how it can be used.
**2. [Sim: 0.414]** Theoretical Framework.
**3. [Sim: 0.410]** good point
**4. [Sim: 0.410]** grammar :)
**5. [Sim: 0.400]** suggestion: 'sufficient amount of patients'

---
## Query 30
**Student Proposal Chunk:**
> augmented...

**Retrieved Feedback:**
**1. [Sim: 0.636]** This term would benefit from a brief definition.
**2. [Sim: 0.571]** Make sure to stay in a scientific writing style, and don't use this many "marketing words" as groundbreaking, transformative etc
**3. [Sim: 0.558]** also seems very general to me - what is the theoretical idea/foundation behind this RQ?
**4. [Sim: 0.530]** RQ2: It does not relate to RQ1 due to its technical nature. Questionably related to the other RQs.
**5. [Sim: 0.524]** Where is the submission date?

---
