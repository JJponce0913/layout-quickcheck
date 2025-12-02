from lqc.generate.web_page.create import save_as_web_page
import pickle


def check_pickled_run_subject(pickle_file):
    pickle_addre = pickle_file
    with open(pickle_addre, "rb") as f:
        run_subject = pickle.load(f)
    print(run_subject)
    print("HTML Tree:")
    print(run_subject.html_tree)
    print("Base Styles:")
    print(run_subject.base_styles)
    print("Modified Styles:")
    print(list(run_subject.modified_styles.getElementIds())[0])
    print(f"Loaded run_subject from {pickle_addre}")

    save_as_web_page(run_subject, "test.html")

check_pickled_run_subject("C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/bug_reports/raw/postSkip-bug-report/postSkip-bug-report-2025-12-02-11-18-18-428332/run_subject_pre.pkl")