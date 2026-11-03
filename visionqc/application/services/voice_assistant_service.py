from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re

from visionqc.application.ports.event_bus import EventBus
from visionqc.application.ports.voice import VoiceConversationRepository
from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.domain.events import DomainEvent
from visionqc.voice.models import VoiceConversation, VoiceIntent, VoiceMessage, VoiceResponse


class VoiceAssistantService:
    """Offline-first operator copilot grounded in Factory Memory.

    It intentionally uses deterministic intent routing and evidence-backed
    responses. Cloud LLM enrichment may be added later without making core
    factory operation dependent on internet connectivity.
    """

    def __init__(self, memory: FactoryMemoryService, conversations: VoiceConversationRepository, event_bus: EventBus, root_cause_service=None, predictive_quality_service=None, factory_engineer_service=None) -> None:
        self._memory = memory; self._conversations = conversations; self._event_bus = event_bus; self._root_cause = root_cause_service; self._predictive = predictive_quality_service; self._factory_engineer = factory_engineer_service

    def new_conversation(self, *, factory_name: str = "", operator_name: str = "", selected_case_id: int | None = None) -> tuple[int, VoiceConversation]:
        conversation = VoiceConversation(factory_name=factory_name, operator_name=operator_name, selected_case_id=selected_case_id)
        cid = self._conversations.save(conversation)
        return cid, conversation

    def ask(self, conversation_id: int, question: str, *, source: str = "typed", speech_confidence: float = 1.0) -> VoiceResponse:
        question = " ".join(question.split()).strip()
        if not question: raise ValueError("متن پرسش الزامی است")
        conversation = self._conversations.get(conversation_id)
        if conversation is None: raise KeyError(f"Conversation {conversation_id} was not found")
        intent, confidence = self._classify(question)
        conversation.messages.append(VoiceMessage(role="operator", text=question, intent=intent, confidence=speech_confidence, source=source))
        response = self._answer(intent, question, conversation.selected_case_id)
        conversation.messages.append(VoiceMessage(role="assistant", text=response.text, intent=response.intent, confidence=response.confidence, source="visionqc", metadata={"evidence": response.evidence, "safety_note": response.safety_note}))
        conversation.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if conversation.title == "Operator conversation": conversation.title = question[:70]
        self._conversations.update(conversation_id, conversation)
        self._event_bus.publish(DomainEvent(name="voice_ai.question_answered", source="voice_assistant_service", payload={"conversation_id": conversation_id, "intent": str(intent), "source": source, "selected_case_id": conversation.selected_case_id}))
        return response

    def select_case(self, conversation_id: int, case_id: int | None) -> None:
        conversation = self._conversations.get(conversation_id)
        if conversation is None: raise KeyError(f"Conversation {conversation_id} was not found")
        if case_id is not None and self._memory.get(case_id) is None: raise KeyError(f"Factory memory case {case_id} was not found")
        conversation.selected_case_id = case_id; conversation.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._conversations.update(conversation_id, conversation)

    def get(self, conversation_id: int) -> VoiceConversation | None: return self._conversations.get(conversation_id)
    def list_recent(self, limit: int = 50): return self._conversations.list_recent(limit)

    @staticmethod
    def _classify(text: str) -> tuple[VoiceIntent, float]:
        q=text.casefold()
        rules=[
            (VoiceIntent.HELP,("help","what can you do","راهنما","چه کاری")),
            (VoiceIntent.SIMILAR_CASES,("similar","same problem","مشابه","سابقه")),
            (VoiceIntent.FACTORY_ENGINEER,("factory engineer","operational briefing","shift briefing","engineer report","مهندس کارخانه","گزارش عملیاتی","گزارش مهندس")),
            (VoiceIntent.PREDICTIVE_RISK,("predict quality","quality risk","forecast","early warning","پیش بینی","پیش‌بینی","ریسک کیفیت","هشدار زودهنگام")),
            (VoiceIntent.REJECT_TREND,("reject increasing","reject trend","rejection","ضایعات","ردی","افزایش رد")),
            (VoiceIntent.RECOMMENDED_ACTIONS,("what should","action","recommend","check first","root cause","why","چه کار","اقدام","پیشنهاد","علت","چرا")),
            (VoiceIntent.DEFECT_SUMMARY,("defect","fault","عیب","نقص")),
            (VoiceIntent.CASE_SUMMARY,("this case","selected case","case summary","این پرونده","خلاصه پرونده")),
            (VoiceIntent.RECENT_CASES,("recent","latest cases","آخرین","اخیر")),
            (VoiceIntent.QUALITY_STATUS,("quality","status","passed","failed","کیفیت","وضعیت")),
            (VoiceIntent.GREETING,("hello","hi","سلام")),
        ]
        for intent,terms in rules:
            if any(t in q for t in terms): return intent,.92
        return VoiceIntent.UNKNOWN,.45

    def _answer(self, intent: VoiceIntent, question: str, selected_case_id: int | None) -> VoiceResponse:
        selected=self._memory.get(selected_case_id) if selected_case_id is not None else None
        recent=self._memory.list_recent(100)
        if intent == VoiceIntent.GREETING:
            return VoiceResponse("سلام. من دستیار هوشمند کنترل کیفیت VisionQC هستم. می‌توانم پرونده انتخاب‌شده را خلاصه کنم، سوابق مشابه کارخانه را بیابم، عیوب را بررسی کنم و کنترل‌های مبتنی بر شواهد پیشنهاد دهم.",intent,.99,suggested_prompts=self._prompts())
        if intent == VoiceIntent.HELP:
            return VoiceResponse("می‌توانید درباره پرونده بازرسی انتخاب‌شده، موارد رد اخیر، عیوب تکرارشونده، سوابق مشابه یا کنترل‌های بعدی سؤال کنید. پاسخ‌ها بر پایه Factory Memory هستند و جایگزین تصمیم کارشناس کنترل کیفیت نیستند.",intent,.99,suggested_prompts=self._prompts())
        if intent == VoiceIntent.FACTORY_ENGINEER:
            if self._factory_engineer is None:
                return VoiceResponse("AI Factory Engineer در این نصب در دسترس نیست.", intent, .6)
            briefing = self._factory_engineer.generate_briefing(case_id=selected_case_id)
            actions = " ".join(f"{i+1}) {a.title}" for i, a in enumerate(briefing.actions[:4]))
            return VoiceResponse(
                f"{briefing.executive_summary} اقدامات اولویت‌دار: {actions}",
                intent, .94, evidence=list(briefing.evidence[:5]),
                safety_note="این پاسخ فقط پشتیبان تصمیم عملیاتی است. گیت‌های تصمیم‌گیری را رعایت کرده و تأیید مجاز دریافت کنید."
            )
        if intent == VoiceIntent.PREDICTIVE_RISK:
            if self._predictive is None:
                return VoiceResponse("Predictive Quality در این نصب در دسترس نیست.",intent,.6)
            product=selected.product_name if selected else None
            line=selected.production.production_line if selected else None
            machine=selected.production.machine_name if selected else None
            f=self._predictive.forecast(product_name=product,line=line or None,machine=machine or None)
            drivers=", ".join(d.name for d in f.drivers[:3]) or "عامل غالب مشخصی یافت نشد"
            actions=" ".join(f"{i+1}) {a}" for i,a in enumerate(f.recommended_actions[:3]))
            return VoiceResponse(f"بررسی پیش‌بینانه کیفیت برای بازه تولید مشابه بعدی، سطح ریسک {f.risk_band} با امتیاز {f.risk_score*100:.0f}٪ را نشان می‌دهد. نرخ پیش‌بینی‌شده رد محصول {f.predicted_reject_rate*100:.1f}٪ است. عوامل اصلی: {drivers}. اقدامات پیشنهادی: {actions}",intent,f.confidence,evidence=[d.explanation for d in f.drivers[:4]],safety_note="این فقط هشدار زودهنگام است. اقدامات باید توسط کنترل کیفیت یا مسئول فرایند تأیید شوند.")
        if intent == VoiceIntent.RECENT_CASES:
            failed=[c for c in recent[:20] if not c.passed]
            return VoiceResponse(f"تعداد {len(recent[:20])} پرونده اخیر در حافظه کارخانه یافت شد که {len(failed)} مورد آن رد شده است. " + ("آخرین محصولات ردشده: " + ", ".join(c.product_name for c in failed[:5]) + "." if failed else "در آخرین سوابق مورد ردشده‌ای وجود ندارد."),intent,.94,evidence=[f"Factory Memory: {len(recent[:20])} latest cases"])
        if intent in {VoiceIntent.CASE_SUMMARY,VoiceIntent.QUALITY_STATUS}:
            if not selected: return self._need_case(intent)
            defects=", ".join(d.defect_type for d in selected.defects) or "موردی ثبت نشده است"
            state="پذیرفته‌شده" if selected.passed else "ردشده"
            text=f"پرونده {selected.case_uuid[:8]} برای محصول {selected.product_name} دارای وضعیت {state} است. عیوب ثبت‌شده: {defects}. خط: {selected.production.production_line or 'ثبت نشده'}؛ دستگاه: {selected.production.machine_name or 'ثبت نشده'}؛ شیفت: {selected.production.shift_name or 'ثبت نشده'}."
            if selected.confirmed_cause: text += f" علت تأییدشده توسط کنترل کیفیت: {selected.confirmed_cause}."
            return VoiceResponse(text,intent,.97,evidence=[f"Selected Factory Memory case {selected.case_uuid}"])
        if intent == VoiceIntent.DEFECT_SUMMARY:
            cases=[selected] if selected else recent[:50]
            names=[d.defect_type for c in cases if c for d in c.defects]
            counts=Counter(names)
            if not counts: return VoiceResponse("در محدوده انتخاب‌شده هیچ مشاهده‌ای از عیب ثبت نشده است.",intent,.9,evidence=["Factory Memory defect records"])
            top=", ".join(f"{name}: {count}" for name,count in counts.most_common(5))
            return VoiceResponse(f"پرتکرارترین عیوب ثبت‌شده عبارت‌اند از: {top}. این فقط شمارش مشاهدات ثبت‌شده است و نتیجه‌گیری علّی محسوب نمی‌شود.",intent,.95,evidence=[f"{sum(counts.values())} stored defect observations"])
        if intent == VoiceIntent.SIMILAR_CASES:
            if not selected: return self._need_case(intent)
            similar=self._memory.find_similar(selected,limit=5)
            if not similar: return VoiceResponse("پرونده تاریخی با شباهت کافی پیدا نشد. برای بهبود Factory Memory، شرایط فرایند و نتایج اقدامات اصلاحی تأییدشده را ثبت کنید.",intent,.9,evidence=["Factory Memory similarity search"])
            parts=[]; evidence=[]
            for item in similar[:3]:
                cause=item.case.confirmed_cause or "علت تأیید نشده"
                parts.append(f"{item.case.product_name}, similarity {item.similarity*100:.0f}%, {cause}")
                evidence.append(f"Case {item.case.case_uuid}: {', '.join(item.matching_signals)}")
            return VoiceResponse("نزدیک‌ترین پرونده‌های تاریخی: " + "; ".join(parts) + ".",intent,.93,evidence=evidence)
        if intent == VoiceIntent.RECOMMENDED_ACTIONS:
            if not selected: return self._need_case(intent)
            if self._root_cause is not None and selected_case_id is not None:
                analysis = self._root_cause.analyze(selected_case_id, limit=3)
                top = analysis.top_hypothesis
                if top is not None:
                    actions = " ".join(f"{i+1}) {a}" for i,a in enumerate(top.recommended_actions)) or "برای تأیید به کارشناس کنترل کیفیت ارجاع دهید."
                    evidence = [e.explanation for e in top.supporting_evidence[:4]]
                    return VoiceResponse(f"فرضیه اصلی: {top.cause}. سطح اطمینان: {top.confidence} ({top.score*100:.0f}٪). بررسی‌های پیشنهادی: {actions} تا زمان تأیید کنترل کیفیت، این علت قطعی محسوب نمی‌شود.", intent, top.score, evidence=evidence, safety_note=analysis.safety_note)
            similar=self._memory.find_similar(selected,limit=8)
            actions=[]; evidence=[]
            for item in similar:
                if item.case.qc_approved:
                    for action in item.case.corrective_actions:
                        if action.status.casefold() in {"completed","verified","effective"} or action.result:
                            actions.append(action.description); evidence.append(f"Verified case {item.case.case_uuid[:8]} ({item.similarity*100:.0f}% similar)")
            unique=list(dict.fromkeys(a for a in actions if a.strip()))[:4]
            if not unique:
                unique=["نور، فوکوس و موقعیت دوربین را بررسی کنید.","محصول، دستور ساخت، بچ و مرحله فرایند را تأیید کنید.","ناحیه تحت‌تأثیر را بررسی و اندازه‌گیری‌های فرایند را ثبت کنید.","پیش از تغییر تنظیمات دستگاه، موضوع را به کنترل کیفیت ارجاع دهید."]
                evidence=["Controlled VisionQC fallback checklist; no verified similar corrective action found"]
            return VoiceResponse("بررسی‌های پیشنهادی: " + " ".join(f"{i+1}) {a}" for i,a in enumerate(unique)),intent,.88,evidence=evidence)
        if intent == VoiceIntent.REJECT_TREND:
            scope=recent[:50]; rejected=[c for c in scope if not c.passed]
            if not scope: return VoiceResponse("Factory Memory هنوز پرونده کافی برای بررسی روند موارد ردشده ندارد.",intent,.7)
            rate=100*len(rejected)/len(scope); counts=Counter(d.defect_type for c in rejected for d in c.defects)
            top=counts.most_common(3)
            detail=(" مهم‌ترین عیوب ثبت‌شده در موارد ردشده: " + ", ".join(f"{n} ({c})" for n,c in top) + ".") if top else ""
            return VoiceResponse(f"در میان آخرین {len(scope)} پرونده، {len(rejected)} مورد رد شده و نرخ ثبت‌شده رد برابر {rate:.1f}٪ است.{detail} تعیین جهت روند به داده‌های زمان‌دار و یک بازه تولید قابل‌مقایسه بزرگ‌تر نیاز دارد.",intent,.9,evidence=["Latest Factory Memory case window"])
        return VoiceResponse("این پرسش به یکی از درخواست‌های کنترل‌شده کارخانه نگاشت نشد. درباره خلاصه پرونده، موارد مشابه، عیوب، روند موارد ردشده یا کنترل‌های پیشنهادی سؤال کنید.",VoiceIntent.UNKNOWN,.45,suggested_prompts=self._prompts())

    @staticmethod
    def _need_case(intent: VoiceIntent) -> VoiceResponse:
        return VoiceResponse("ابتدا یک پرونده از Factory Memory انتخاب کنید تا پاسخ بر اساس همان پرونده و سوابق مشابه ارائه شود.",intent,.99,suggested_prompts=["این پرونده را خلاصه کن","موارد مشابه را پیدا کن","ابتدا چه چیزی را بررسی کنم؟"])
    @staticmethod
    def _prompts() -> list[str]: return ["این پرونده را خلاصه کن","موارد مشابه را پیدا کن","ریسک کیفیت را پیش‌بینی کن","ابتدا چه چیزی را بررسی کنم؟"]
