
import time
import array

from digits_data import digits

from everywhere_digits import RandomForestClassifier
import m2c_digits
import emltrees


def emlearn_create():
    model = emltrees.new(7, 150)

    # Load a CSV file with the model
    with open('eml_digits.csv', 'r') as f:
        emltrees.load_model(model, f)
    return model

def argmax(l):
    max_value = l[0]
    max_idx = 0
    for i, v in enumerate(l):
        if v > max_value:
            max_value = v
            max_idx = i
    return max_idx


clf = RandomForestClassifier()
def everywhere_run(data):
    errors = 0
    for idx, x in enumerate(data):
        #x = array.array('f', x)
        out = clf.predict(x)
        if (idx != out):
            errors += 1
    return errors

model = emlearn_create()
def emlearn_run(data):
    errors = 0
    for idx, x in enumerate(data):
        out = model.predict(x)
        if (idx != out):
            errors += 1
    return errors

def m2c_run(data):
    errors = 0
    for idx, x in enumerate(data):
        #x = array.array('f', x)
        scores = m2c_digits.score(x)
        out = argmax(scores)
        if (idx != out):
            errors += 1
    return errors

def none_run(data):
    errors = 0
    for idx, x in enumerate(data):
        #tmp = len(x)
        out = idx
        if (idx != out):
            errors += 1
    return errors

def benchmark():

    import gc

    #data = digits
    data = [ array.array('h', x) for x in digits ]


    print('model,errors,time_us')

    gc.collect()
    before = time.ticks_us()
    none_errors = none_run(data)
    gc.collect()
    after = time.ticks_us()
    none_duration = time.ticks_diff(after, before)
    print('none,{},{}'.format(none_errors, none_duration))

    gc.collect()
    before = time.ticks_us()
    eml_errors = emlearn_run(data)
    gc.collect()
    after = time.ticks_us()
    eml_duration = time.ticks_diff(after, before)
    print('emlearn,{},{}'.format(eml_errors, eml_duration))

    gc.collect()
    before = time.ticks_us()
    everywhere_errors = everywhere_run(data)
    gc.collect()
    after = time.ticks_us()
    everywhere_duration = time.ticks_diff(after, before)
    print('everywhere,{},{}'.format(everywhere_errors, everywhere_duration))

    gc.collect()
    before = time.ticks_us()
    m2c_errors = m2c_run(data)
    gc.collect()
    after = time.ticks_us()
    m2c_duration = time.ticks_diff(after, before)
    print('m2cgen,{},{}'.format(m2c_errors, m2c_duration))


