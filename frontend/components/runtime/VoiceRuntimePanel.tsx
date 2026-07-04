"use client"

import { useEffect, useState } from "react"

import {

    Mic,

    AudioLines,

    Brain,

    Sparkles,

    Activity,

    Volume2,

    Ear,

    Radio

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// TRANSCRIPT
// ==========================================

interface Transcript {

    text: string

    timestamp: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function VoiceRuntimePanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        listening,

        setListening

    ] = useState(false)

    const [

        speaking,

        setSpeaking

    ] = useState(false)

    const [

        wakeWordDetected,

        setWakeWordDetected

    ] = useState(false)

    const [

        transcripts,

        setTranscripts

    ] = useState<Transcript[]>([])

    const [

        activeVoice,

        setActiveVoice

    ] = useState("jarvis_male")

    const [

        runtimeEvents,

        setRuntimeEvents

    ] = useState<string[]>([])


    // ==========================================
    // WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (

            event: CognitionEvent
        ) => {

            // ======================================
            // FILTER VOICE EVENTS
            // ======================================

            const isVoiceEvent = (

                event.agent ===
                "voice_runtime"

                ||

                event.agent ===
                "speech_to_text_engine"
            )

            if (!isVoiceEvent) {

                return
            }

            // ======================================
            // STORE EVENTS
            // ======================================

            setRuntimeEvents(

                (previous) => [

                    event.message,

                    ...previous
                ].slice(0, 15)
            )

            // ======================================
            // LISTENING
            // ======================================

            if (

                event.event_type ===
                "voice_listening_started"
            ) {

                setListening(true)
            }

            // ======================================
            // SPEECH RECOGNIZED
            // ======================================

            if (

                event.event_type ===
                "speech_recognition_completed"
            ) {

                setListening(false)

                const transcript =

                    event.payload
                    ?.recognized_text

                if (transcript) {

                    setTranscripts(

                        (previous) => [

                            {

                                text:
                                    transcript,

                                timestamp:
                                    new Date()
                                    .toISOString()
                            },

                            ...previous
                        ].slice(0, 20)
                    )

                    // ==============================
                    // WAKE WORD
                    // ==============================

                    const lower = (
                        transcript.toLowerCase()
                    )

                    if (

                        lower.includes(
                            "hey cortex"
                        )

                        ||

                        lower.includes(
                            "cortex"
                        )

                        ||

                        lower.includes(
                            "jarvis"
                        )
                    ) {

                        setWakeWordDetected(
                            true
                        )

                        setTimeout(() => {

                            setWakeWordDetected(
                                false
                            )

                        }, 4000)
                    }
                }
            }

            // ======================================
            // SPEAKING
            // ======================================

            if (

                event.event_type ===
                "voice_synthesis_started"
            ) {

                setSpeaking(true)
            }

            if (

                event.event_type ===
                "voice_synthesis_completed"
            ) {

                setSpeaking(false)

                const profile =

                    event.payload
                    ?.voice_profile

                if (profile) {

                    setActiveVoice(
                        profile
                    )
                }
            }
        }

        websocketService.subscribe(
            handleEvent
        )

        return () => {

            websocketService.unsubscribe(
                handleEvent
            )
        }

    }, [])


    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="

                rounded-2xl

                border
                border-[#4a8c70]/20

                bg-gradient-to-br

                from-slate-950
                via-slate-900
                to-black

                p-6

                shadow-2xl
                shadow-[#82c0a4]/10
            "
        >

            {/* HEADER */}

            <div
                className="
                    flex
                    items-center
                    justify-between
                    mb-6
                "
            >

                <div
                    className="
                        flex
                        items-center
                        gap-3
                    "
                >

                    <div
                        className="
                            p-3

                            rounded-xl

                            bg-[#4a8c70]/10

                            border
                            border-[#82c0a4]/20
                        "
                    >

                        <Mic
                            className="
                                w-6
                                h-6
                                text-[#4a8c70]
                            "
                        />

                    </div>

                    <div>

                        <h2
                            className="
                                text-xl
                                font-bold
                                text-white
                            "
                        >

                            Voice Runtime

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Realtime Conversational
                            Intelligence Runtime

                        </p>

                    </div>

                </div>

                <div
                    className="
                        flex
                        items-center
                        gap-2

                        px-4
                        py-2

                        rounded-full

                        bg-emerald-500/10

                        border
                        border-emerald-400/20
                    "
                >

                    <Activity
                        className="
                            w-4
                            h-4
                            text-emerald-400
                            animate-pulse
                        "
                    />

                    <span
                        className="
                            text-sm
                            text-emerald-300
                            font-medium
                        "
                    >

                        VOICE ONLINE

                    </span>

                </div>

            </div>


            {/* STATUS GRID */}

            <div
                className="
                    grid
                    grid-cols-1
                    md:grid-cols-4
                    gap-4
                    mb-6
                "
            >

                {/* LISTENING */}

                <div
                    className="
                        rounded-xl

                        bg-white/5

                        border
                        border-white/10

                        p-4
                    "
                >

                    <div
                        className="
                            flex
                            items-center
                            gap-2
                            mb-2
                        "
                    >

                        <Ear
                            className="
                                w-4
                                h-4
                                text-[#4a8c70]
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Listening

                        </span>

                    </div>

                    <div
                        className={`
                            text-lg
                            font-bold

                            ${
                                listening
                                    ? "text-emerald-400"
                                    : "text-slate-500"
                            }
                        `}
                    >

                        {listening
                            ? "ACTIVE"
                            : "IDLE"}

                    </div>

                </div>


                {/* SPEAKING */}

                <div
                    className="
                        rounded-xl

                        bg-white/5

                        border
                        border-white/10

                        p-4
                    "
                >

                    <div
                        className="
                            flex
                            items-center
                            gap-2
                            mb-2
                        "
                    >

                        <Volume2
                            className="
                                w-4
                                h-4
                                text-[#82c0a4]
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Speaking

                        </span>

                    </div>

                    <div
                        className={`
                            text-lg
                            font-bold

                            ${
                                speaking
                                    ? "text-[#82c0a4]"
                                    : "text-slate-500"
                            }
                        `}
                    >

                        {speaking
                            ? "SPEAKING"
                            : "SILENT"}

                    </div>

                </div>


                {/* WAKE WORD */}

                <div
                    className="
                        rounded-xl

                        bg-white/5

                        border
                        border-white/10

                        p-4
                    "
                >

                    <div
                        className="
                            flex
                            items-center
                            gap-2
                            mb-2
                        "
                    >

                        <Sparkles
                            className="
                                w-4
                                h-4
                                text-yellow-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Wake Word

                        </span>

                    </div>

                    <div
                        className={`
                            text-lg
                            font-bold

                            ${
                                wakeWordDetected
                                    ? "text-yellow-400"
                                    : "text-slate-500"
                            }
                        `}
                    >

                        {wakeWordDetected
                            ? "DETECTED"
                            : "WAITING"}

                    </div>

                </div>


                {/* VOICE PROFILE */}

                <div
                    className="
                        rounded-xl

                        bg-white/5

                        border
                        border-white/10

                        p-4
                    "
                >

                    <div
                        className="
                            flex
                            items-center
                            gap-2
                            mb-2
                        "
                    >

                        <Brain
                            className="
                                w-4
                                h-4
                                text-emerald-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Voice Profile

                        </span>

                    </div>

                    <div
                        className="
                            text-sm
                            font-bold
                            text-white
                        "
                    >

                        {activeVoice}

                    </div>

                </div>

            </div>


            {/* TRANSCRIPTS */}

            <div
                className="
                    mb-6
                "
            >

                <h3
                    className="
                        text-sm
                        font-semibold
                        text-slate-300
                        mb-3
                    "
                >

                    Live Conversation Stream

                </h3>

                <div
                    className="
                        space-y-3

                        max-h-[320px]
                        overflow-y-auto
                    "
                >

                    {transcripts.map(

                        (
                            transcript,
                            index
                        ) => (

                            <div
                                key={index}

                                className="
                                    p-4

                                    rounded-xl

                                    bg-white/5

                                    border
                                    border-white/10
                                "
                            >

                                <div
                                    className="
                                        flex
                                        items-center
                                        gap-2
                                        mb-2
                                    "
                                >

                                    <AudioLines
                                        className="
                                            w-4
                                            h-4
                                            text-[#4a8c70]
                                        "
                                    />

                                    <span
                                        className="
                                            text-xs
                                            text-slate-500
                                        "
                                    >

                                        {new Date(
                                            transcript.timestamp
                                        ).toLocaleTimeString()}

                                    </span>

                                </div>

                                <p
                                    className="
                                        text-sm
                                        text-slate-200
                                        leading-relaxed
                                    "
                                >

                                    {transcript.text}

                                </p>

                            </div>
                        )
                    )}

                    {transcripts.length === 0 && (

                        <div
                            className="
                                flex
                                flex-col
                                items-center
                                justify-center

                                py-14

                                text-center
                            "
                        >

                            <Radio
                                className="
                                    w-12
                                    h-12
                                    text-[#4a8c70]
                                    mb-4
                                "
                            />

                            <h3
                                className="
                                    text-lg
                                    font-semibold
                                    text-white
                                    mb-2
                                "
                            >

                                Awaiting Voice Input

                            </h3>

                            <p
                                className="
                                    text-slate-400
                                    max-w-md
                                "
                            >

                                CortexPrime is ready for
                                realtime conversational
                                interaction and wake-word
                                activation.

                            </p>

                        </div>
                    )}

                </div>

            </div>


            {/* EVENT FEED */}

            <div>

                <h3
                    className="
                        text-sm
                        font-semibold
                        text-slate-300
                        mb-3
                    "
                >

                    Voice Runtime Telemetry

                </h3>

                <div
                    className="
                        space-y-2
                    "
                >

                    {runtimeEvents.map(

                        (
                            event,
                            index
                        ) => (

                            <div
                                key={index}

                                className="
                                    rounded-lg

                                    bg-[#4a8c70]/5

                                    border
                                    border-[#82c0a4]/10

                                    px-4
                                    py-3
                                "
                            >

                                <div
                                    className="
                                        flex
                                        items-center
                                        gap-2
                                    "
                                >

                                    <Activity
                                        className="
                                            w-4
                                            h-4
                                            text-[#4a8c70]
                                        "
                                    />

                                    <span
                                        className="
                                            text-sm
                                            text-slate-200
                                        "
                                    >

                                        {event}

                                    </span>

                                </div>

                            </div>
                        )
                    )}

                </div>

            </div>

        </div>
    )
}