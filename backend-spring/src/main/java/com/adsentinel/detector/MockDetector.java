package com.adsentinel.detector;

import com.adsentinel.crawler.ElementRecord;
import com.adsentinel.result.Finding;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public class MockDetector implements Detector {
    private static final Set<Integer> CONFUSABLES = Set.of(
            0x0430, 0x0435, 0x043E, 0x0440, 0x0441, 0x0445, 0x0455,
            0x0391, 0x0395, 0x039F, 0x03A1, 0x03A7, 0x03BF, 0x03C1
    );

    @Override
    public List<Finding> detect(List<ElementRecord> elements) {
        List<Finding> findings = new ArrayList<>();
        int sequence = 1;
        for (ElementRecord element : elements) {
            String text = element.text() == null ? "" : element.text();
            if (isNormalInterfaceElement(element, text)) continue;
            String jamoReason = jamoReason(text);
            if (jamoReason != null) findings.add(finding(sequence++, element, "JAMO", jamoReason));

            String homoglyphReason = homoglyphReason(text);
            if (homoglyphReason != null) findings.add(finding(sequence++, element, "HOMOGLYPH", homoglyphReason));

            String transparentReason = transparentReason(element);
            if (transparentReason != null) findings.add(finding(sequence++, element, "TRANSPARENT", transparentReason));

            if (element.hiddenReasons().contains("offscreen")) {
                findings.add(finding(sequence++, element, "OFFSCREEN", "요소의 boundingClientRect가 viewport 밖에 있음"));
            }
        }
        return findings;
    }

    private Finding finding(int sequence, ElementRecord element, String technique, String reason) {
        return new Finding("f_%03d".formatted(sequence), element.url(), true,
                element.location(), element.text(), technique, reason);
    }

    private String jamoReason(String text) {
        int jamoCount = 0;
        for (int i = 0; i < text.length(); i++) {
            int codePoint = text.codePointAt(i);
            if ((codePoint >= 0x1100 && codePoint <= 0x11FF) ||
                    (codePoint >= 0x3130 && codePoint <= 0x318F) ||
                    (codePoint >= 0xA960 && codePoint <= 0xA97F) ||
                    (codePoint >= 0xD7B0 && codePoint <= 0xD7FF)) {
                jamoCount++;
            }
        }
        return jamoCount >= 2 && text.codePointCount(0, text.length()) <= 300
                ? "한글 자모/호환 자모 코드포인트 포함" : null;
    }

    private String homoglyphReason(String text) {
        boolean hasLatin = false;
        boolean hasConfusable = false;
        for (int i = 0; i < text.length(); i++) {
            int codePoint = text.codePointAt(i);
            if (Character.UnicodeScript.of(codePoint) == Character.UnicodeScript.LATIN) hasLatin = true;
            if (CONFUSABLES.contains(codePoint)) hasConfusable = true;
        }
        if (hasConfusable) return "라틴 문자와 혼동될 수 있는 그리스/키릴 문자 포함";
        if (hasLatin && text.matches(".*[\\u0370-\\u03FF\\u0400-\\u04FF].*")) {
            return "라틴 문자와 그리스/키릴 문자가 혼합됨";
        }
        return null;
    }

    private String transparentReason(ElementRecord element) {
        List<String> reasons = element.hiddenReasons();
        if (reasons.contains("display:none")) return "display:none";
        if (reasons.contains("visibility:hidden")) return "visibility:hidden";
        if (reasons.contains("opacity:0")) return "opacity:0 또는 조상 opacity 누적값 0";
        if (reasons.contains("zero-size")) return "boundingClientRect 크기 0";
        if (reasons.contains("font-size:0")) return "font-size:0";
        Map<String, Object> style = element.style();
        String opacity = String.valueOf(style.getOrDefault("opacity", "1")).toLowerCase(Locale.ROOT);
        return "0".equals(opacity) ? "computed opacity:0" : null;
    }

    private boolean isNormalInterfaceElement(ElementRecord element, String text) {
        String normalized = text.replaceAll("\\s+", " ").trim().toLowerCase(Locale.ROOT);
        if (normalized.isBlank()) return true;
        String location = element.location() == null ? "" : element.location().toLowerCase(Locale.ROOT);
        if (location.contains("#tab-") || location.contains("#gnb-") ||
                location.contains("#tit_total_sch") || location.contains("#mobile-nav") ||
                location.contains("#mgnb-")) return true;
        if (normalized.contains("정보공개제도") && normalized.length() < 180) return true;
        if (normalized.length() > 300 && (normalized.contains("메인메뉴") ||
                normalized.contains("본문 바로가기") || normalized.contains("전체메뉴"))) return true;
        return normalized.contains("메인메뉴 바로가기") || normalized.contains("본문 바로가기") ||
                normalized.equals("language english 中文 日本語") || normalized.equals("전체메뉴") ||
                normalized.equals("이전화면") || normalized.equals("검색 닫기") ||
                normalized.startsWith("copyright ") || normalized.equals("정보공개") ||
                normalized.equals("행정정보공개") || normalized.equals("참여·소통") ||
                normalized.equals("알림·자료") || normalized.equals("기관소개") ||
                normalized.equals("정보공개제도") || normalized.equals("기상청 소개") ||
                normalized.equals("청렴정보공개") || normalized.equals("청렴자료공개") ||
                normalized.equals("공유") || normalized.matches("\\(0?2\\)[- )0-9]+") ||
                normalized.equals("전체메뉴 닫기") || normalized.equals("통합검색") ||
                normalized.equals("블로그") || normalized.equals("공지사항") ||
                normalized.equals("공지사항 리스트") || normalized.equals("new") ||
                normalized.equals("기상콜센터") || normalized.equals("1") ||
                normalized.equals("1 / 3");
    }
}
