from evaluation.m9b_formal_analysis import family_macro_auprc,primary_decision
def test_decision_gate():
 assert primary_decision(.05,.001,True)=="PASS"
 assert primary_decision(.049,.1,True)=="FAIL"
 assert primary_decision(.2,.1,False)=="insufficient_support"
def test_macro_ap():
 eps=[{"family":f,"samples":[{"danger":True,"R1":2},{"danger":False,"R1":1}]} for f in [f"F{i}" for i in range(1,8)]]
 assert family_macro_auprc(eps,"R1")==1
