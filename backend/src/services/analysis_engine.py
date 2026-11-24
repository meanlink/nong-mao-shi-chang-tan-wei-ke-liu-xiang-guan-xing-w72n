import math
from collections import defaultdict
VARIABLES=['footfall','transactions','revenue']
def rank(values):
    order=sorted(range(len(values)),key=lambda i:values[i]);out=[0.0]*len(values);i=0
    while i<len(order):
        j=i
        while j+1<len(order) and values[order[j+1]]==values[order[i]]:j+=1
        value=(i+j)/2+1
        for k in range(i,j+1):out[order[k]]=value
        i=j+1
    return out
def corr(x,y):
    if len(x)<3 or len(set(x))<2 or len(set(y))<2:return 0.0
    mx=sum(x)/len(x);my=sum(y)/len(y);num=sum((a-mx)*(b-my) for a,b in zip(x,y));den=math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y));return round(num/den,4) if den else 0.0
def solve(matrix,vector):
    n=len(vector);a=[list(row)+[vector[i]] for i,row in enumerate(matrix)]
    for col in range(n):
        pivot=max(range(col,n),key=lambda row:abs(a[row][col]))
        if abs(a[pivot][col])<1e-10:return [0.0]*n
        a[col],a[pivot]=a[pivot],a[col];base=a[col][col];a[col]=[v/base for v in a[col]]
        for row in range(n):
            if row!=col:
                factor=a[row][col];a[row]=[a[row][j]-factor*a[col][j] for j in range(n+1)]
    return [a[i][-1] for i in range(n)]
def residual(values,controls):
    design=[[1.0]+[c[i] for c in controls] for i in range(len(values))];xtx=[[sum(row[i]*row[j] for row in design) for j in range(len(design[0]))] for i in range(len(design[0]))];xty=[sum(design[k][i]*values[k] for k in range(len(values))) for i in range(len(design[0]))];beta=solve(xtx,xty);return [values[i]-sum(design[i][j]*beta[j] for j in range(len(beta))) for i in range(len(values))]
def spearman(x,y):return corr(rank(x),rank(y))
def partial(x,y,controls):
    if len(x)<5:return 0.0
    return corr(residual(rank(x),[rank(c) for c in controls]),residual(rank(y),[rank(c) for c in controls]))
def lag_matrix(rows):
    ordered=sorted(rows,key=lambda s:s['sampled_at']);series={k:[float(s[k]) for s in ordered] for k in VARIABLES};matrix=[]
    for lag in [-2,-1,0,1,2]:
        row={'lag':lag}
        for left in VARIABLES:
            for right in VARIABLES:
                if lag>=0:a,b=series[left][lag:],series[right][:len(series[right])-lag or None]
                else:shift=abs(lag);a,b=series[left][:-shift],series[right][shift:]
                row[f'{left}_vs_{right}']=spearman(a,b) if len(a)>=3 else 0.0
        matrix.append(row)
    return matrix
def analyze_samples(rows):
    problems=[]
    if len(rows)<12:problems.append('样本时段不足，至少需要 12 个有效时段')
    for row in rows:
        if row['status']!='valid':problems.append(row.get('issue_reason') or '样本状态不可解释')
    if problems:return {'explainable':False,'reason':'；'.join(dict.fromkeys(problems)),'sample_count':len(rows),'valid_count':sum(r['status']=='valid' for r in rows),'partial_matrix':[],'lag_matrix':[],'stall_findings':[],'headline':'本次样本不满足招商解释条件'}
    controls=[[float(r['dwell_seconds']) for r in rows],[float(r['hour_index']) for r in rows]];partial_matrix=[]
    for i,left in enumerate(VARIABLES):
        for right in VARIABLES[i+1:]:
            value=partial([float(r[left]) for r in rows],[float(r[right]) for r in rows],controls);partial_matrix.append({'x':left,'y':right,'value':value,'direction':'正相关' if value>=0 else '负相关'})
    grouped=defaultdict(list)
    for row in rows:grouped[row['stall_code']].append(row)
    findings=[]
    for code,items in grouped.items():
        flow=sum(r['footfall'] for r in items)/len(items);conversion=sum(r['transactions'] for r in items)/max(sum(r['footfall'] for r in items),1);revenue=sum(r['revenue'] for r in items)/max(sum(r['footfall'] for r in items),1)
        findings.append({'stall_code':code,'samples':len(items),'avg_footfall':round(flow,1),'conversion_rate':round(conversion,4),'revenue_per_visit':round(revenue,4),'signal':'优先招商' if conversion>=.16 and flow>=70 else ('观察' if conversion>=.12 else '复核')})
    findings.sort(key=lambda x:(x['conversion_rate'],x['avg_footfall']),reverse=True)
    return {'explainable':True,'reason':'样本量、活动标签与时间序列均通过复核','sample_count':len(rows),'valid_count':len(rows),'partial_matrix':partial_matrix,'lag_matrix':lag_matrix(rows),'stall_findings':findings,'headline':f'客流与成交的偏相关为 {partial_matrix[0]["value"]:.2f}，可用于招商复核','method':'Spearman 秩变换后，以停留时长与小时序号为控制变量做残差相关。滞后矩阵按采样时段顺序计算 -2 至 +2 时段的秩相关。'}
