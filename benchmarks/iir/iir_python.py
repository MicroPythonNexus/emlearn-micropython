
import array


class IIRFilter():
    def __init__(self, coefficients : array.array):
        stages = len(coefficients)//6

        self.sos = coefficients
        self.state = array.array('f', [0.0]*(2*stages))

    @micropython.native
    def process(self, samples : array.array):
        """Filter incoming data with cascaded second-order sections.
        """

        stages = len(self.sos)//6

        # iterate over all samples
        for i in range(len(samples)):
            x = samples[i]

            # apply all filter sections
            for s in range(stages):
                b0, b1, b2, a0, a1, a2 = self.sos[s*6:(s*6)+6]

                # compute difference equations of transposed direct form II
                y = b0*x + self.state[(s*2)+0]
                self.state[(s*2)+0] = b1*x - a1*y + self.state[(s*2)+1]
                self.state[(s*2)+1] = b2*x - a2*y
                # set biquad output as input of next filter section
                x = y

            # assign to output
            samples[i] = x

        return None
