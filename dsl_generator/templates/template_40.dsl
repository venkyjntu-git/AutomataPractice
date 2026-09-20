AUTOMATA DFA

template_id: DFA_Kth_SYMBOL_END

pattern_family: {Nth symbol from end}

difficulty: 3

description:
Construct a DFA that accepts all strings where K th symbol from end is A.  

alphabet:
    size: 2
    symbol_pools:
        {a,b,c}
        {0,1}

roles:{
    A <- alpha[0]

}
parameters:
    K in [2,5]

condition:
   length >= K
   kth_from_end(K, A)
     

testing:
    cases: 200
    max_length: 50

tags: {dfa, nth symbol from end}

closure_allowed: true 
END
