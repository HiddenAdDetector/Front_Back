package com.adsentinel.crawler;

import com.adsentinel.detector.Detector;
import com.adsentinel.result.Finding;
import com.adsentinel.result.ResultMeta;
import com.adsentinel.result.ResultWriter;
import com.adsentinel.result.SubmissionResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.microsoft.playwright.*;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.*;
import java.util.concurrent.*;

@Service
public class CrawlService {
    private static final int MAX_PAGES = 100;
    private static final int MAX_QUEUE = 500;
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final Map<String, Map<String, Object>> jobs = new ConcurrentHashMap<>();
    private final Map<String, Future<?>> tasks = new ConcurrentHashMap<>();
    private final Detector detector;
    private final ResultWriter resultWriter;

    public CrawlService(Detector detector, ResultWriter resultWriter) {
        this.detector = detector;
        this.resultWriter = resultWriter;
    }

    public String start(String url) {
        String id = UUID.randomUUID().toString();
        Map<String, Object> job = new ConcurrentHashMap<>();
        job.put("status", "queued"); job.put("url", url); job.put("progress", Map.of());
        job.put("findings", Collections.synchronizedList(new ArrayList<Finding>()));
        job.put("logs", Collections.synchronizedList(new ArrayList<String>()));
        jobs.put(id, job); tasks.put(id, executor.submit(() -> run(id, canonicalize(url))));
        return id;
    }

    public Map<String, Object> status(String id) {
        Map<String, Object> job = jobs.get(id);
        if (job == null) throw new NoSuchElementException("crawl job not found");
        return Map.copyOf(job);
    }

    public void stop(String id) {
        Map<String, Object> job = jobs.get(id);
        if (job == null) return;
        job.put("status", "stopping");
        Future<?> task = tasks.get(id);
        if (task != null) task.cancel(true);
    }

    private void run(String id, String entryUrl) {
        Map<String, Object> job = jobs.get(id); job.put("status", "running");
        Instant started = Instant.now();
        List<ElementRecord> elements = new ArrayList<>();
        List<String> visited = new ArrayList<>();
        List<Map<String, String>> failures = new ArrayList<>();
        Queue<String> queue = new ArrayDeque<>(); Set<String> seen = new HashSet<>();
        queue.add(entryUrl); seen.add(entryUrl);
        String host = URI.create(entryUrl).getHost();

        try (Playwright playwright = Playwright.create()) {
            Browser browser = playwright.chromium().launch(new BrowserType.LaunchOptions().setHeadless(true));
            BrowserContext context = browser.newContext();
            try {
                while (!queue.isEmpty() && visited.size() < MAX_PAGES && !Thread.currentThread().isInterrupted()) {
                    String url = queue.poll(); Page page = context.newPage();
                    addLog(job, "OPEN", "페이지 열기: " + url);
                    job.put("progress", progress(visited.size(), queue.size(), failures.size(), elements.size(), url, page, "opening"));
                    try {
                        try {
                            page.navigate(url, new Page.NavigateOptions().setTimeout(30_000));
                            addLog(job, "NAVIGATE", "DOM 로드 완료: " + url);
                        } catch (TimeoutError timeout) {
                            addLog(job, "TIMEOUT_CONTINUE", "페이지 로드 시간 초과. 현재 DOM을 계속 수집합니다: " + url);
                        }
                        job.put("progress", progress(visited.size(), queue.size(), failures.size(), elements.size(), url, page, "dom_loaded"));
                        List<ElementRecord> pageElements = extract(page, url);
                        elements.addAll(pageElements);
                        addLog(job, "EXTRACT", "DOM/CSS 수집 완료: " + pageElements.size() + "개 요소");
                        job.put("progress", progress(visited.size(), queue.size(), failures.size(), elements.size(), url, page, "dom_extracted"));
                        List<Finding> liveFindings = deduplicate(detector.detect(pageElements));
                        @SuppressWarnings("unchecked")
                        List<Finding> currentFindings = (List<Finding>) job.get("findings");
                        mergeFindings(currentFindings, liveFindings);
                        @SuppressWarnings("unchecked") List<String> hrefs = (List<String>) page.locator("a[href]").evaluateAll("els => els.map(e => e.href)");
                        for (String href : hrefs) addInternalLink(href, host, queue, seen);
                        addLog(job, "DISCOVER", "내부 링크 " + hrefs.size() + "개 발견, 대기 " + queue.size() + "개");
                        visited.add(url);
                    } catch (Exception ex) {
                        addLog(job, "ERROR", "페이지 오류: " + messageOf(ex));
                        failures.add(Map.of("url", url, "error", messageOf(ex)));
                    }
                    addLog(job, "COMPLETE", "페이지 처리 완료: " + url);
                    job.put("progress", progress(visited.size(), queue.size(), failures.size(), elements.size(), url, page, "page_complete"));
                    page.close();
                }
            } finally { context.close(); browser.close(); }

            String stopReason = Thread.currentThread().isInterrupted() ? "user_stop" :
                    queue.isEmpty() ? "queue_empty" :
                    visited.size() >= MAX_PAGES ? "max_pages_reached" : "completed";
            addLog(job, "STOP_REASON", "탐색 종료 사유: " + stopReason + ", 남은 대기 페이지: " + queue.size());
            Instant finished = Instant.now();
            List<Finding> findings = deduplicate(detector.detect(elements));
            ResultMeta meta = new ResultMeta("공공 웹사이트 불법광고 탐지", entryUrl, started.toString(), finished.toString(), Duration.between(started, finished).toSeconds(), "1.0.0");
            SubmissionResult result = new SubmissionResult(meta, findings);
            resultWriter.write(result, List.of());
            Map<String, Object> report = buildReport(entryUrl, started, finished, visited, failures, elements, findings, stopReason);
            resultWriter.writeReport(report);
            addLog(job, "DONE", "전체 탐색 완료: " + visited.size() + "개 페이지");
            job.put("result", result); job.put("report", report); job.put("findings", findings); job.put("progress", progress(visited.size(), queue.size(), failures.size(), elements.size(), "", null, stopReason));
            job.put("status", Thread.currentThread().isInterrupted() ? "stopped" : "completed");
        } catch (Exception ex) { job.put("status", "failed"); job.put("error", messageOf(ex)); }
    }

    private List<Finding> deduplicate(List<Finding> findings) {
        Map<String, Finding> unique = new LinkedHashMap<>();
        for (Finding finding : findings) unique.putIfAbsent(canonicalize(finding.url()) + "\u0000" + finding.location() + "\u0000" + finding.technique(), finding);
        return new ArrayList<>(unique.values());
    }

    private Map<String, Object> buildReport(String entryUrl, Instant started, Instant finished,
                                            List<String> visited, List<Map<String, String>> failures,
                                            List<ElementRecord> elements, List<Finding> findings,
                                            String stopReason) {
        Map<String, Long> techniqueCounts = new LinkedHashMap<>();
        for (Finding finding : findings) techniqueCounts.merge(finding.technique(), 1L, Long::sum);
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("report_type", "candidate_detection_report");
        report.put("model_status", "not_connected");
        report.put("review_required", true);
        report.put("message", "현재 결과는 DOM/CSS 규칙 기반 후보이며 탐지 모델 연결 후 확정 판정이 필요합니다.");
        report.put("entry_url", entryUrl);
        report.put("started_at", started.toString());
        report.put("finished_at", finished.toString());
        report.put("stop_reason", stopReason);
        report.put("visited_pages", visited.size());
        report.put("failed_pages", failures.size());
        report.put("extracted_elements", elements.size());
        report.put("candidate_count", findings.size());
        report.put("technique_counts", techniqueCounts);
        report.put("findings", findings);
        return report;
    }

    private void mergeFindings(List<Finding> target, List<Finding> additions) {
        synchronized (target) {
            List<Finding> merged = new ArrayList<>(target);
            merged.addAll(additions);
            target.clear();
            target.addAll(deduplicate(merged));
        }
    }

    private Map<String, Object> progress(int visited, int queued, int failed, int elements, String currentUrl, Page page, String phase) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("visited_pages", visited); result.put("queued_pages", queued); result.put("failed_pages", failed);
        result.put("extracted_elements", elements); result.put("current_url", currentUrl);
        result.put("last_progress_at", Instant.now().toString()); result.put("phase", phase); result.put("engine", "Playwright Java");
        result.put("max_pages", MAX_PAGES); result.put("max_queue", MAX_QUEUE);
        result.put("browser_status", page == null ? "closed" : "running");
        if (page != null) {
            try { result.put("screenshot_data_url", "data:image/png;base64," + Base64.getEncoder().encodeToString(page.screenshot(new Page.ScreenshotOptions().setFullPage(false)))); }
            catch (Exception ignored) { }
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    private void addLog(Map<String, Object> job, String type, String message) {
        List<String> logs = (List<String>) job.get("logs");
        synchronized (logs) {
            logs.add("[" + Instant.now() + "][" + type + "] " + message);
            if (logs.size() > 100) logs.remove(0);
        }
    }

    private void addInternalLink(String href, String host, Queue<String> queue, Set<String> seen) {
        try {
            URI link = URI.create(href); if (!("http".equals(link.getScheme()) || "https".equals(link.getScheme())) || !host.equals(link.getHost())) return;
            String clean = canonicalize(href); if (seen.add(clean) && queue.size() < MAX_QUEUE) queue.add(clean);
        } catch (Exception ignored) { }
    }

    private String canonicalize(String raw) {
        URI uri = URI.create(raw); List<String> query = new ArrayList<>();
        if (uri.getQuery() != null) query.addAll(Arrays.asList(uri.getQuery().split("&")));
        query.sort(String::compareTo);
        String queryText = String.join("&", query);
        try { return new URI(uri.getScheme().toLowerCase(), uri.getAuthority().toLowerCase(), uri.getPath() == null || uri.getPath().isBlank() ? "/" : uri.getPath(), queryText.isBlank() ? null : queryText, null).toString(); }
        catch (Exception ex) { return raw.split("#", 2)[0]; }
    }

    private String messageOf(Exception exception) { return exception.getMessage() == null ? exception.getClass().getSimpleName() : exception.getMessage(); }

    @SuppressWarnings("unchecked")
    private List<ElementRecord> extract(Page page, String url) {
        List<ElementRecord> records = new ArrayList<>();
        for (Frame frame : page.frames()) {
            try {
                Object evaluated = frame.evaluate("""
                    (props) => Array.from(document.querySelectorAll('a,span,div,p,li,td,small,em,strong,h1,h2,h3,h4,h5,h6')).filter(e => {
                      const ownText=Array.from(e.childNodes).filter(n => n.nodeType===Node.TEXT_NODE).map(n => n.textContent||'').join('').trim();
                      return ownText.length > 0 || e.children.length === 0;
                    }).filter(e => e.textContent !== '').map(e => {
                      const s=getComputedStyle(e), r=e.getBoundingClientRect(), hidden=[]; let n=e, effectiveOpacity=1;
                      while(n){const x=getComputedStyle(n); effectiveOpacity*=Number.parseFloat(x.opacity||'1'); if(x.display==='none')hidden.push('display:none'); if(x.visibility==='hidden'||x.visibility==='collapse')hidden.push('visibility:hidden'); if(x.opacity==='0')hidden.push('opacity:0'); n=n.parentElement;}
                      if(r.width===0||r.height===0)hidden.push('zero-size');
                      const outsideViewport=r.right < -50 || r.bottom < -50 || r.left > innerWidth + 50 || r.top > innerHeight + 50;
                      if((s.position==='absolute'||s.position==='fixed') && outsideViewport)hidden.push('offscreen');
                      if(s.fontSize==='0px')hidden.push('font-size:0');
                      const selector=e.id?'#'+CSS.escape(e.id):e.tagName.toLowerCase(); const style={}; props.forEach(p=>style[p]=s[p]);
                      return {location:selector,text:e.textContent,context:e.parentElement?.textContent||'',style,bbox:{x:r.x,y:r.y,width:r.width,height:r.height},visible:hidden.length===0&&effectiveOpacity>0,hiddenReasons:[...new Set(hidden)]};
                    })
                    """, List.of("display","visibility","opacity","color","backgroundColor","fontSize","position","top","left","right","bottom","transform","clip","clipPath","overflow","width","height","zIndex"));
                if (!(evaluated instanceof List<?> raw)) continue;
                String frameLocation = frame.parentFrame() == null ? "" : "iframe[src=\"" + frame.url() + "\"] >>> ";
                for (Object value : raw) {
                    if (!(value instanceof Map<?, ?> item)) continue;
                    String location = frameLocation + String.valueOf(valueOr(item, "location", ""));
                    String text = String.valueOf(valueOr(item, "text", "")); String context = String.valueOf(valueOr(item, "context", ""));
                    Map<String, Object> style = (Map<String, Object>) valueOr(item, "style", Map.of());
                    Map<String, Double> bbox = (Map<String, Double>) valueOr(item, "bbox", Map.of());
                    List<String> hidden = (List<String>) valueOr(item, "hiddenReasons", List.of());
                    records.add(new ElementRecord(url, location, frame.parentFrame() == null ? List.of() : List.of(frameLocation), text, context, style, bbox, Boolean.TRUE.equals(item.get("visible")), hidden, frame.url()));
                }
            } catch (Exception ignored) { }
        }
        return records;
    }

    private Object valueOr(Map<?, ?> map, String key, Object fallback) { Object value = map.get(key); return value == null ? fallback : value; }
}
