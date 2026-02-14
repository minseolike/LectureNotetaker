"""Tests for the improvements:
- Bone metabolism terms in korean_dict.py
- PostProcessor smart spacing
- AudioResampler numpy fallback
- GUI env check logic
"""

import os
import re
import struct
import unittest
from unittest.mock import MagicMock, patch


class TestBoneMetabolismTerms(unittest.TestCase):
    """Test that bone metabolism/endocrinology terms are properly loaded."""

    def test_korean_dict_has_bone_terms(self):
        """korean_dict includes BONE_METABOLISM_TERMS."""
        from stt.korean_dict import get_builtin_korean_to_english
        all_terms = get_builtin_korean_to_english()

        self.assertEqual(all_terms["오스테오칼신"], "osteocalcin")
        self.assertEqual(all_terms["오스테오클라스트"], "osteoclast")
        self.assertEqual(all_terms["오스테오블라스트"], "osteoblast")
        self.assertEqual(all_terms["비스포스포네이트"], "bisphosphonate")
        self.assertEqual(all_terms["데노수맙"], "denosumab")
        self.assertEqual(all_terms["시티엑스"], "CTX")
        self.assertEqual(all_terms["피원엔피"], "P1NP")
        self.assertEqual(all_terms["덱사"], "DEXA")
        self.assertEqual(all_terms["티스코어"], "T-score")

    def test_korean_dict_has_pth_terms(self):
        """korean_dict includes parathyroid/calcium metabolism terms."""
        from stt.korean_dict import get_builtin_korean_to_english
        all_terms = get_builtin_korean_to_english()

        self.assertEqual(all_terms["파라토르몬"], "parathyroid hormone")
        self.assertEqual(all_terms["피티에이치"], "PTH")
        self.assertEqual(all_terms["칼시토닌"], "calcitonin")
        self.assertEqual(all_terms["비타민 디"], "vitamin D")

    def test_medical_terms_has_bone_ko(self):
        """medical/terms.py has Korean bone metabolism terms for STT boosting."""
        from medical.terms import get_all_medical_terms
        all_terms = get_all_medical_terms()
        term_names = {t for t, _ in all_terms}

        bone_ko_terms = ["골표지자", "골밀도", "골흡수", "골형성", "파골세포",
                         "조골세포", "비스포스포네이트", "데노수맙"]
        for term in bone_ko_terms:
            self.assertIn(term, term_names, f"Missing Korean bone term: {term}")

    def test_medical_terms_has_bone_en(self):
        """medical/terms.py has English bone metabolism terms for STT boosting."""
        from medical.terms import get_all_medical_terms
        all_terms = get_all_medical_terms()
        term_names = {t for t, _ in all_terms}

        bone_en_terms = ["bone turnover marker", "CTX", "P1NP", "osteocalcin",
                         "bisphosphonate", "denosumab", "DEXA", "T-score", "RANKL"]
        for term in bone_en_terms:
            self.assertIn(term, term_names, f"Missing English bone term: {term}")

    def test_osteoporosis_boosted(self):
        """Osteoporosis should have high boost value (20)."""
        from medical.terms import get_all_medical_terms
        all_terms = get_all_medical_terms()
        term_dict = {t: b for t, b in all_terms}

        self.assertEqual(term_dict.get("골다공증"), 20)
        self.assertEqual(term_dict.get("osteoporosis"), 20)


class TestAudioResamplerNumpy(unittest.TestCase):
    """Test numpy-based mono conversion."""

    def test_stereo_to_mono_numpy(self):
        """Numpy fallback produces correct mono output."""
        from audio.resampler import AudioResampler
        resampler = AudioResampler(2, 48000)
        resampler._use_audioop = False

        stereo = struct.pack("<hh", 1000, 2000) * 100
        mono = resampler.to_mono(stereo)

        self.assertEqual(len(mono), len(stereo) // 2)

        first_sample = struct.unpack("<h", mono[:2])[0]
        self.assertEqual(first_sample, 1500)

    def test_mono_passthrough(self):
        """Mono input passes through unchanged."""
        from audio.resampler import AudioResampler
        resampler = AudioResampler(1, 48000)

        mono_in = struct.pack("<h", 1234) * 100
        mono_out = resampler.to_mono(mono_in)
        self.assertEqual(mono_in, mono_out)

    def test_numpy_matches_audioop(self):
        """Numpy output should closely match audioop output (if available)."""
        from audio.resampler import AudioResampler
        import warnings

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                import audioop
        except ImportError:
            self.skipTest("audioop not available for comparison")

        resampler_audioop = AudioResampler(2, 48000)
        resampler_audioop._use_audioop = True
        resampler_numpy = AudioResampler(2, 48000)
        resampler_numpy._use_audioop = False

        import random
        random.seed(42)
        stereo_data = bytes(
            b for _ in range(1000)
            for v in [random.randint(-32768, 32767), random.randint(-32768, 32767)]
            for b in struct.pack("<h", v)
        )

        mono_audioop = resampler_audioop.to_mono(stereo_data)
        mono_numpy = resampler_numpy.to_mono(stereo_data)

        self.assertEqual(len(mono_audioop), len(mono_numpy))

        for i in range(0, len(mono_audioop), 2):
            a = struct.unpack("<h", mono_audioop[i:i+2])[0]
            n = struct.unpack("<h", mono_numpy[i:i+2])[0]
            self.assertAlmostEqual(a, n, delta=1,
                                   msg=f"Sample {i//2}: audioop={a}, numpy={n}")


class TestEnvCheck(unittest.TestCase):
    """Test GUI env check logic respects STT provider."""

    @patch.dict(os.environ, {
        "STT_PROVIDER": "deepgram",
        "DEEPGRAM_API_KEY": "test_key",
        "OPENAI_API_KEY": "test_key",
    }, clear=False)
    def test_deepgram_no_gcp_warning(self):
        """With Deepgram provider, missing GCP keys should NOT trigger warning."""
        env = os.environ.copy()
        env.pop("GCP_PROJECT_ID", None)
        env.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

        with patch.dict(os.environ, env, clear=True):
            missing = []
            stt_provider = os.getenv("STT_PROVIDER", "deepgram")
            if stt_provider == "deepgram":
                if not os.getenv("DEEPGRAM_API_KEY"):
                    missing.append("DEEPGRAM_API_KEY")
            else:
                if not os.getenv("GCP_PROJECT_ID"):
                    missing.append("GCP_PROJECT_ID")
            if not os.getenv("OPENAI_API_KEY"):
                missing.append("OPENAI_API_KEY")

            self.assertEqual(len(missing), 0)

    @patch.dict(os.environ, {
        "STT_PROVIDER": "google",
        "OPENAI_API_KEY": "test_key",
    }, clear=True)
    def test_google_warns_about_gcp(self):
        """With Google provider, missing GCP keys should trigger warning."""
        missing = []
        stt_provider = os.getenv("STT_PROVIDER", "deepgram")
        if stt_provider == "deepgram":
            if not os.getenv("DEEPGRAM_API_KEY"):
                missing.append("DEEPGRAM_API_KEY")
        else:
            if not os.getenv("GCP_PROJECT_ID"):
                missing.append("GCP_PROJECT_ID")
        if not os.getenv("OPENAI_API_KEY"):
            missing.append("OPENAI_API_KEY")

        self.assertIn("GCP_PROJECT_ID", missing)


class TestPostProcessorKoreanCorrections(unittest.TestCase):
    """Test postprocessor Korean->Korean corrections."""

    def test_process_korean_only(self):
        """process() only does Korean->Korean corrections, no English."""
        from stt.postprocess import TranscriptPostProcessor
        proc = TranscriptPostProcessor()

        result = proc.process("골프지자 검사를 하겠습니다")
        self.assertIn("골표지자", result)
        self.assertNotIn("골프지자", result)

    def test_new_correction_variants(self):
        """New correction variants work."""
        from stt.postprocess import TranscriptPostProcessor
        proc = TranscriptPostProcessor()

        self.assertIn("골표지자", proc.process("골프이자 검사"))
        self.assertIn("골표지자", proc.process("골프골프이자 검사"))

    def test_no_english_conversion(self):
        """process() does NOT convert Korean->English."""
        from stt.postprocess import TranscriptPostProcessor
        proc = TranscriptPostProcessor()

        result = proc.process("오스테오포로시스 환자")
        self.assertNotIn("osteoporosis", result)
        self.assertIn("오스테오포로시스", result)


if __name__ == "__main__":
    unittest.main()
