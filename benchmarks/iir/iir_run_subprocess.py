
import os
import array
import tempfile
import subprocess

import npyfile


here = os.path.dirname(__file__)


def run_iir(data : array.array,
        coefficients : array.array,
        micropython_bin='micropython',
    ):

    script_path = os.path.join(here, 'iir_run.py')

    with tempfile.TemporaryDirectory() as temp_dir:

        filter_path = os.path.join(temp_dir, 'filter.npy')
        input_path = os.path.join(temp_dir, 'input.npy')
        output_path = os.path.join(temp_dir, 'output.npy')

        # write input data to files
        npyfile.save(filter_path, coefficients)
        npyfile.save(input_path, data)

        assert not os.path.exists(output_path), output_path

        # run the processing function
        args = [
            micropython_bin,
            script_path,
            input_path,
            output_path,
            filter_path,            
        ]
        cmd = ' '.join(args)

        print('run: ', cmd)

        out = subprocess.check_output(args)
        print(out)

        # load the output
        assert os.path.exists(output_path), output_path
        output_shape, output = npyfile.load(output_path)

        return output
