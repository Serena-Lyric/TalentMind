import pytest
from app.collect.schema import RawJD
from app.collect.cleaner import clean, _strip_noise, _extract_duties, _extract_experience


class TestStripNoise:
    def test_removes_pay_line(self):
        text = "Leading real estate firm\nPay: $18-20/hour\nGreat culture"
        result = _strip_noise(text)
        assert "Pay:" not in result
        assert "Leading real estate firm" in result
        assert "Great culture" in result

    def test_removes_benefits_line(self):
        text = "Cool startup\nBenefits:Paid time off\nFun team"
        result = _strip_noise(text)
        assert "Benefits:" not in result
        assert "Cool startup" in result

    def test_removes_schedule_line(self):
        text = "Exciting role\nSchedule:8 hour shift\nApply now"
        result = _strip_noise(text)
        assert "Schedule:" not in result

    def test_removes_location_line(self):
        text = "Remote friendly\nWork Location: In person\nJoin us"
        result = _strip_noise(text)
        assert "Work Location:" not in result

    def test_removes_job_type_line(self):
        text = "Great job\nJob Type: Full-time\nApply"
        result = _strip_noise(text)
        assert "Job Type:" not in result

    def test_removes_salary_amount_line(self):
        text = "Awesome role\n$65,000 - $85,000 per year\nJoin us"
        result = _strip_noise(text)
        assert "$65,000" not in result

    def test_fixes_fused_prefix(self):
        text = "Job descriptionA leading real estate firm is seeking..."
        result = _strip_noise(text)
        assert result.startswith("A leading")
        assert "Job description" not in result

    def test_fixes_job_summary_fused(self):
        text = "Job SummaryWe are looking for a skilled engineer..."
        result = _strip_noise(text)
        assert result.startswith("We are looking")

    def test_preserves_normal_text(self):
        text = "We are looking for a Python developer with 5 years of experience."
        result = _strip_noise(text)
        assert result == text


class TestExtractDuties:
    def test_extracts_responsibilities_section(self):
        text = "About us\nWe are a company.\nResponsibilities:\n- Build APIs\n- Review code\n\nQualifications:\nBS degree"
        result = _extract_duties(text)
        assert "Build APIs" in result
        assert "Review code" in result
        assert "BS degree" not in result   # qualifications 后的不应包含

    def test_extracts_what_you_will_do(self):
        text = "Overview\nWhat you'll do:\nDesign systems\nWrite tests\n\nRequirements:\nPython"
        result = _extract_duties(text)
        assert "Design systems" in result
        assert "Python" not in result

    def test_extracts_essential_functions(self):
        text = "Intro\nEssential Functions:\n- Task A\n- Task B\n\nEducation:"
        result = _extract_duties(text)
        assert "Task A" in result
        assert "Education:" not in result

    def test_returns_empty_when_no_duties_header(self):
        text = "Just a plain job description without any section headers."
        result = _extract_duties(text)
        assert result == ""


class TestExtractExperience:
    def test_uses_fallback_when_provided(self):
        result = _extract_experience("some text", "Entry level")
        assert result == "Entry level"

    def test_extracts_from_text_when_no_fallback(self):
        text = "Overview\nExperience: 3-5 years in software development\nSkills: Python"
        result = _extract_experience(text, "")
        assert "3-5 years" in result

    def test_returns_empty_when_nothing_found(self):
        result = _extract_experience("Just a job description.", "")
        assert result == ""


class TestClean:
    def test_clean_produces_jd_pool_row(self):
        raw = RawJD(
            source="linkedin",
            job_title="  AI Engineer ",
            raw_html=(
                "Job descriptionWe are seeking an AI Engineer.\n"
                "Responsibilities:\n- Build RAG systems\n- Deploy models\n"
                "Pay: $50/hour\nBenefits:Full coverage\n"
                "Experience: 3-5 years\nWork Location: Remote"
            ),
            duties="",
            experience="",
        )
        row = clean(raw)
        assert row["source"] == "linkedin"
        assert row["job_title"] == "AI Engineer"
        assert "Pay:" not in row["raw_text"]
        assert "Benefits:" not in row["raw_text"]
        assert "Build RAG systems" in row["duties"]
        assert "3-5 years" in row["experience"]
        assert row["status"] == "cleaned"
        assert row["crawled_at"] is not None
