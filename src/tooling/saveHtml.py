pickle_addre="C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/bug_reports/test-repo/safe/safe_1767679263.pkl"
import pickle
from lqc.generate.web_page.create import save_as_web_page

with open(pickle_addre, "rb") as f:
    run_subject = pickle.load(f)
print(f"Loaded run_subject from {pickle_addre}")
save_as_web_page(run_subject, "test.html")
